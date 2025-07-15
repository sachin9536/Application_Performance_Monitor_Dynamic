import os
import time
import requests

# Only run if DEMO_MODE=1
if os.getenv("DEMO_MODE") != "1":
    print("[register_demo_services] DEMO_MODE not enabled, skipping auto-registration.")
    exit(0)

# List of demo services (name, url)
DEMO_SERVICES = [
    ("service_alpha", "http://service_alpha:8000"),
    ("service_beta", "http://service_beta:8000"),
    ("service_gamma", "http://service_gamma:8000"),
    ("dummy_service", "http://dummy_service:9000"),
    ("service_delta", "http://service_delta:9400"),
]

API_URL = os.getenv("API_URL", "http://monitoring_engine_demo:8000")
REGISTER_ENDPOINT = f"{API_URL}/api/demo/register_services"

# Wait for backend to be up (up to 2 minutes)
max_retries = 60
for attempt in range(max_retries):
    try:
        resp = requests.get(f"{API_URL}/api/health", timeout=2)
        if resp.status_code == 200:
            print(f"[register_demo_services] Monitoring backend is up! (after {attempt+1} tries)")
            break
    except Exception:
        print(f"[register_demo_services] Waiting for backend... ({attempt+1}/{max_retries})")
    time.sleep(2)
else:
    print("[register_demo_services] Monitoring backend not reachable, aborting.")
    exit(1)

# Register each demo service
for name, url in DEMO_SERVICES:
    try:
        resp = requests.post(REGISTER_ENDPOINT, json={"name": name, "url": url}, timeout=3)
        if resp.status_code == 200:
            print(f"[register_demo_services] Registered {name} ({url})")
        elif resp.status_code == 400 and "already exists" in resp.text:
            print(f"[register_demo_services] {name} already registered.")
        else:
            print(f"[register_demo_services] Failed to register {name}: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[register_demo_services] Exception registering {name}: {e}") 