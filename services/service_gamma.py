from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app, Counter, Histogram, Gauge, CollectorRegistry
import time
import random
import psutil
import logging

app = FastAPI()
registry = CollectorRegistry()
SERVICE = "service_gamma"

# Prometheus Metrics
REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["service", "status"], registry=registry)
ERRORS = Counter("errors_total", "Total errors", ["service"], registry=registry)

# APM-style breakdown metrics
TTFB = Histogram("ttfb_ms", "Time to first byte (ms)", ["service"], buckets=[50, 100, 200, 300, 400], registry=registry)
SERVER = Histogram("server_processing_ms", "Server processing time (ms)", ["service"], buckets=[100, 200, 300, 500], registry=registry)
DB = Histogram("db_query_ms", "DB query time (ms)", ["service"], buckets=[100, 200, 400, 800], registry=registry)
TOTAL = Histogram("total_response_ms", "Total response time (ms)", ["service"], buckets=[300, 600, 1000, 1500], registry=registry)

# Legacy/aggregate latency metric (optional)
LATENCY = Histogram("response_latency_ms", "Response latency (ms)", ["service"], buckets=[100, 300, 600, 1000], registry=registry)

MEMORY_MB = Gauge("memory_used_mb", "Memory used MB", ["service"], registry=registry)
CPU_PERCENT = Gauge("cpu_percent", "CPU usage percent", ["service"], registry=registry)
UP = Gauge("up", "Service up status (1=up, 0=down)", ["service"], registry=registry)

# Memory bloat simulation
memory_bloat = []

# Mount /metrics
app.mount("/metrics", make_asgi_app(registry=registry))

@app.on_event("startup")
def mark_up():
    UP.labels(SERVICE).set(1)

@app.on_event("shutdown")
def mark_down():
    UP.labels(SERVICE).set(0)

@app.get("/")
def root():
    # Randomly simulate crash
    if random.random() < 0.05:
        UP.labels(SERVICE).set(0)
        time.sleep(3)
        UP.labels(SERVICE).set(1)

    # Simulate APM breakdown timings
    ttfb = random.uniform(60, 180)
    server = random.uniform(120, 250)
    db = random.uniform(200, 600)
    total = ttfb + server + db

    # Observe breakdown metrics
    TTFB.labels(SERVICE).observe(ttfb)
    SERVER.labels(SERVICE).observe(server)
    DB.labels(SERVICE).observe(db)
    TOTAL.labels(SERVICE).observe(total)
    LATENCY.labels(SERVICE).observe(total)  # For legacy/aggregate

    # Simulate error
    status = 200
    if random.random() < 0.15:
        ERRORS.labels(SERVICE).inc()
        status = 500
        logging.error(f"Simulated error in {SERVICE}: returning 500")

    # Simulate memory bloat
    memory_bloat.append(bytearray(random.randint(50000, 100000)))

    # System stats
    CPU_PERCENT.labels(SERVICE).set(psutil.cpu_percent(interval=0.1))
    MEMORY_MB.labels(SERVICE).set(psutil.virtual_memory().used / 1024 / 1024)

    REQUESTS.labels(SERVICE, str(status)).inc()
    time.sleep(total / 1000)
    return JSONResponse(content={"message": "Hello from service gamma!"}, status_code=status)

@app.get("/health")
def health():
    return {"status": "ok"}
