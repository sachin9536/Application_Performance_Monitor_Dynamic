import asyncio
import aiohttp
import random
import time
import os
import platform
import logging
import json
from datetime import datetime
from typing import Dict, List
import uuid

# Determine log directory: prefer /app/logs (Docker), fallback to ./logs (local)
LOG_DIR = "logs"
LOG_PATH = os.path.join(LOG_DIR, "metrics.log")

# Create logs directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # Only log the message (which will be JSON)
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)

def log_json(level, message, service=None, **kwargs):
    log_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": service if service else "controller",
        "message": message,
    }
    log_data.update(kwargs)
    logging.info(json.dumps(log_data))

def truncate_log_file(log_path=LOG_PATH, max_size_mb=10, keep_lines=10000):
    import os
    if not os.path.exists(log_path):
        return
    size_mb = os.path.getsize(log_path) / (1024 * 1024)
    if size_mb > max_size_mb:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        lines = lines[-keep_lines:]
        with open(log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[Log Rotation] Truncated {log_path} to last {keep_lines} lines (was {size_mb:.2f} MB)")

# Backend API URL for service discovery
MONITORING_ENGINE_URL = os.getenv("MONITORING_ENGINE_URL", "http://localhost:8000")

# --- JWT Auth Support ---
TEST_USER_EMAIL = os.getenv("CONTROLLER_USER_EMAIL", "testuser@example.com")
TEST_USER_PASSWORD = os.getenv("CONTROLLER_USER_PASSWORD", "testpass123")

async def get_jwt_token(session):
    login_url = f"{MONITORING_ENGINE_URL}/login"
    payload = {"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    async with session.post(login_url, json=payload) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data.get("access_token")
        else:
            log_json("ERROR", f"Failed to log in: {resp.status}")
            return None

async def fetch_registered_services(session, jwt_token):
    # Use the new endpoint that returns ALL registered services (no auth required)
    try:
        async with session.get(f"{MONITORING_ENGINE_URL}/api/all_registered_services", timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("registered_services", [])
            else:
                log_json("ERROR", f"Failed to fetch registered services: {resp.status}")
                return []
    except Exception as e:
        log_json("ERROR", "Exception fetching registered services", error=str(e))
        return []

# Add a global loop counter
global_loop_count = 0

async def ping_service(session, service, jwt_token, loop_count):
    url = service.get("url")
    name = service.get("name")
    headers = {"Authorization": f"Bearer {jwt_token}"} if jwt_token else {}
    # Always hit healthy endpoints
    endpoints = ["/", "/health", "/slow"]
    for endpoint in endpoints:
        request_id = f"req_{uuid.uuid4()}"
        headers.update({
            "X-Requesting-Service": "controller",
            "X-Target-Service": name,
            "X-Request-ID": request_id
        })
        try:
            start = time.time()
            async with session.get(url.rstrip("/") + endpoint, headers=headers, timeout=5) as resp:
                latency = (time.time() - start) * 1000
                try:
                    response_body = await resp.text()
                except Exception:
                    response_body = "<unreadable>"
                log_json(
                    "INFO",
                    f"GET {endpoint} on {name} responded {resp.status} in {latency:.1f}ms",
                    service=name,
                    status=resp.status,
                    endpoint=endpoint,
                    latency_ms=latency,
                    request_method="GET",
                    request_id=request_id,
                    response_body=response_body[:200]  # Truncate if too large
                )
        except Exception as e:
            log_json(
                "ERROR",
                f"GET {endpoint} on {name} failed: {str(e)}",
                service=name,
                endpoint=endpoint,
                request_method="GET",
                request_id=request_id,
                error_type=type(e).__name__,
                error_message=str(e)
            )
    # Only hit error endpoints every 5th loop
    if loop_count % 5 == 0:
        for endpoint in ["/error/500", "/error/400"]:
            request_id = f"req_{uuid.uuid4()}"
            headers.update({
                "X-Requesting-Service": "controller",
                "X-Target-Service": name,
                "X-Request-ID": request_id
            })
            try:
                start = time.time()
                async with session.get(url.rstrip("/") + endpoint, headers=headers, timeout=5) as resp:
                    latency = (time.time() - start) * 1000
                    try:
                        response_body = await resp.text()
                    except Exception:
                        response_body = "<unreadable>"
                    log_level = "ERROR" if resp.status >= 400 else "INFO"
                    log_json(
                        log_level,
                        f"GET {endpoint} on {name} responded {resp.status} in {latency:.1f}ms",
                        service=name,
                        status=resp.status,
                        endpoint=endpoint,
                        latency_ms=latency,
                        request_method="GET",
                        request_id=request_id,
                        response_body=response_body[:200]
                    )
            except Exception as e:
                log_json(
                    "ERROR",
                    f"GET {endpoint} on {name} failed: {str(e)}",
                    service=name,
                    endpoint=endpoint,
                    request_method="GET",
                    request_id=request_id,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )

async def main():
    request_rate = 5  # initial RPM
    increase_interval = 300
    start_time = time.time()
    loop_count = 0
    async with aiohttp.ClientSession() as session:
        jwt_token = await get_jwt_token(session)
        if not jwt_token:
            print("Failed to obtain JWT token. Exiting.")
            return
        while True:
            truncate_log_file()  # Truncate log if needed before generating traffic
            services = await fetch_registered_services(session, jwt_token)
            if not services:
                log_json("WARNING", "No registered services found. Waiting...")
                await asyncio.sleep(10)
                continue
            tasks = [ping_service(session, svc, jwt_token, loop_count) for svc in services]
            await asyncio.gather(*tasks)
            if time.time() - start_time > increase_interval:
                request_rate = int(request_rate * 1.2)
                start_time = time.time()
            loop_count += 1
            await asyncio.sleep(60 / max(request_rate, 1))

if __name__ == "__main__":
    if platform.system() == "Emscripten":
        asyncio.ensure_future(main())
    else:
        asyncio.run(main())
