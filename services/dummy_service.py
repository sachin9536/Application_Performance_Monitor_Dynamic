from fastapi import FastAPI
from prometheus_client import Counter, Summary, Gauge, make_asgi_app, CollectorRegistry
import time
import random
import psutil
import threading
import os

app = FastAPI()

# Use a custom registry to avoid duplicate errors
registry = CollectorRegistry()

SERVICE_NAME = "dummy_service"

# Metrics with service label
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["service", "status"], registry=registry)
REQUEST_LATENCY = Summary("http_request_duration_seconds", "Request duration in seconds", ["service"], registry=registry)
memory_used_mb = Gauge("memory_used_mb", "Memory usage in MB", ["service"], registry=registry)
CPU_PERCENT = Gauge("cpu_percent", "CPU usage percent", ["service"], registry=registry)
ERRORS_TOTAL = Counter("errors_total", "Total errors", ["service"], registry=registry)
UP = Gauge("up", "Service up status (1=up, 0=down)", ["service"], registry=registry)

# Expose /metrics on the same port as FastAPI
app.mount("/metrics", make_asgi_app(registry=registry))

@app.on_event("startup")
def set_up_metric():
    UP.labels(service=SERVICE_NAME).set(1)
    # Start background thread to simulate periodic requests if enabled
    if os.getenv("SELF_TRAFFIC", "0") == "1":
        print("[dummy_service] SELF_TRAFFIC enabled: starting periodic requests.")
        threading.Thread(target=periodic_requests, daemon=True).start()
    else:
        print("[dummy_service] SELF_TRAFFIC disabled: not starting periodic requests.")

@app.on_event("shutdown")
def set_down_metric():
    UP.labels(service=SERVICE_NAME).set(0)

def update_process_metrics():
    proc = psutil.Process()
    # Memory in MB, rounded to 2 decimals
    mem_mb = round(proc.memory_info().rss / 1024 / 1024, 2)
    memory_used_mb.labels(service=SERVICE_NAME).set(mem_mb)
    # CPU percent (over 0.1s interval), rounded to 2 decimals
    cpu = round(proc.cpu_percent(interval=0.1), 2)
    CPU_PERCENT.labels(service=SERVICE_NAME).set(cpu)

@app.get("/")
@REQUEST_LATENCY.labels(service=SERVICE_NAME).time()
def root():
    status_code = 200
    # Simulate errors
    if random.random() < 0.1:
        ERRORS_TOTAL.labels(service=SERVICE_NAME).inc()
        status_code = 500
    REQUEST_COUNT.labels(service=SERVICE_NAME, status=str(status_code)).inc()
    update_process_metrics()
    time.sleep(random.uniform(0.1, 0.5))
    return {"message": "Hello from dummy service!"}

def periodic_requests():
    import requests
    while True:
        try:
            requests.get("http://localhost:9000/")
        except Exception:
            pass
        time.sleep(5)  # Send a request every 5 seconds

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dummy_service:app", host="0.0.0.0", port=9000, reload=False)