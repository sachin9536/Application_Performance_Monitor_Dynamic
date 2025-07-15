from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app, Counter, Histogram, Gauge, CollectorRegistry
import time
import random
import psutil
import logging

app = FastAPI()
registry = CollectorRegistry()
SERVICE = "service_alpha"

# Prometheus Metrics
REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["service", "status"], registry=registry)
ERRORS = Counter("errors_total", "Total errors", ["service"], registry=registry)

TTFB = Histogram(
    "ttfb_ms", "Time to first byte (ms)", ["service"],
    buckets=[50, 100, 150, 200, 300, 500], registry=registry
)
SERVER = Histogram(
    "server_processing_ms", "Server processing time (ms)", ["service"],
    buckets=[50, 100, 200, 400, 600], registry=registry
)
DB = Histogram(
    "db_query_ms", "DB query time (ms)", ["service"],
    buckets=[20, 50, 100, 150, 200], registry=registry
)
TOTAL = Histogram(
    "total_response_ms", "Total response time (ms)", ["service"],
    buckets=[100, 250, 500, 1000], registry=registry
)

CPU = Gauge("cpu_percent", "CPU usage percent", ["service"], registry=registry)
MEM = Gauge("memory_used_mb", "Memory used MB", ["service"], registry=registry)

# Mount metrics endpoint
app.mount("/metrics", make_asgi_app(registry=registry))


@app.get("/")
async def root(request: Request):
    # Log service identification headers
    requesting_service = request.headers.get("X-Requesting-Service", "unknown")
    target_service = request.headers.get("X-Target-Service", "unknown")
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    logging.info(f"Service Alpha received request from {requesting_service} targeting {target_service} (ID: {request_id})")
    
    # Simulate component durations
    ttfb = random.uniform(50, 150)
    server = random.uniform(50, 200)
    db = random.uniform(20, 100)
    total = ttfb + server + db

    # Observe timings
    TTFB.labels(SERVICE).observe(ttfb)
    SERVER.labels(SERVICE).observe(server)
    DB.labels(SERVICE).observe(db)
    TOTAL.labels(SERVICE).observe(total)

    # System metrics
    CPU.labels(SERVICE).set(psutil.cpu_percent(interval=0.1))
    MEM.labels(SERVICE).set(psutil.virtual_memory().used / 1024 / 1024)

    # Simulate error
    status_code = 200
    if random.random() < 0.1:
        ERRORS.labels(SERVICE).inc()
        status_code = 500
        logging.error(f"Simulated error in {SERVICE}: returning 500")

    # Count requests with status
    REQUESTS.labels(SERVICE, str(status_code)).inc()

    time.sleep(total / 1000)  # Simulate real latency
    return JSONResponse(content={
        "message": "Hello from service alpha!",
        "requested_by": requesting_service,
        "target_service": target_service,
        "request_id": request_id
    }, status_code=status_code)


@app.get("/health")
def health():
    return {"status": "ok"}
