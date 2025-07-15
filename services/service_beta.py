from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app, Counter, Histogram, Gauge, CollectorRegistry
import time
import random
import psutil
import math
import logging

app = FastAPI()
registry = CollectorRegistry()
SERVICE = "service_beta"

# Prometheus Metrics
REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["service", "status"], registry=registry)
ERRORS = Counter("errors_total", "Total errors", ["service"], registry=registry)

TTFB = Histogram("ttfb_ms", "Time to first byte (ms)", ["service"], buckets=[50, 100, 200, 300, 400], registry=registry)
SERVER = Histogram("server_processing_ms", "Server processing time (ms)", ["service"], buckets=[100, 200, 300, 500], registry=registry)
DB = Histogram("db_query_ms", "DB query time (ms)", ["service"], buckets=[100, 200, 400, 800], registry=registry)
TOTAL = Histogram("total_response_ms", "Total response time (ms)", ["service"], buckets=[300, 600, 1000, 1500], registry=registry)

CPU = Gauge("cpu_percent", "CPU usage percent", ["service"], registry=registry)
MEM = Gauge("memory_used_mb", "Memory used MB", ["service"], registry=registry)

app.mount("/metrics", make_asgi_app(registry=registry))


@app.get("/")
async def root(request: Request):
    # Log service identification headers
    requesting_service = request.headers.get("X-Requesting-Service", "unknown")
    target_service = request.headers.get("X-Target-Service", "unknown")
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logging.info(f"Service Beta received request from {requesting_service} targeting {target_service} (ID: {request_id})")
    
    # Simulate timing components
    ttfb = random.uniform(80, 180)
    server = random.uniform(150, 300)
    db = random.uniform(300, 700)  # Heavier DB latency
    total = ttfb + server + db

    # Record timings
    TTFB.labels(SERVICE).observe(ttfb)
    SERVER.labels(SERVICE).observe(server)
    DB.labels(SERVICE).observe(db)
    TOTAL.labels(SERVICE).observe(total)

    # Simulate high CPU load
    heavy_compute_loop()

    # System metrics
    CPU.labels(SERVICE).set(psutil.cpu_percent(interval=0.2))
    MEM.labels(SERVICE).set(psutil.virtual_memory().used / 1024 / 1024)

    # Error simulation (20% failure rate)
    status_code = 200
    if random.random() < 0.2:
        ERRORS.labels(SERVICE).inc()
        status_code = 500
        logging.error(f"Simulated error in {SERVICE}: returning 500")

    # Request count
    REQUESTS.labels(SERVICE, str(status_code)).inc()

    time.sleep(total / 1000)
    return JSONResponse(content={
        "message": "Hello from service beta!",
        "requested_by": requesting_service,
        "target_service": target_service,
        "request_id": request_id
    }, status_code=status_code)


@app.get("/health")
def health():
    return {"status": "ok"}


def heavy_compute_loop():
    # Simulate CPU-bound logic (e.g., large prime calculation)
    for _ in range(100000):
        math.sqrt(random.random() * random.randint(1, 10000))
