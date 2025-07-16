from prometheus_client import CollectorRegistry, start_http_server, Counter, Histogram, Gauge, Summary
import psutil
import time
import threading
from datetime import datetime

# System metrics
# Use a custom registry to avoid duplicated timeseries error
registry = CollectorRegistry()
cpu_percent = Gauge("cpu_percent", "CPU usage percent", ["service"], registry=registry)
memory_used = Gauge("memory_used_mb", "Used memory in MB", ["service"], registry=registry)
process_start_time = Gauge("process_start_time_seconds", "Start time of the process since unix epoch in seconds", ["service"], registry=registry)

# HTTP metrics (industry standard)
http_requests_total = Counter(
    "http_requests_total", 
    "Total HTTP requests", 
    ["method", "endpoint", "status"],
    registry=registry
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry
)

# Business metrics
order_operations_total = Counter(
    "order_operations_total",
    "Total order operations",
    ["operation", "status"],  # operation: create/read, status: success/failure
    registry=registry
)

orders_total = Gauge(
    "orders_total",
    "Total number of orders",
    registry=registry
)

order_value_total = Counter(
    "order_value_total",
    "Total value of all orders",
    ["currency"],
    registry=registry
)

# External service calls
external_service_calls_total = Counter(
    "external_service_calls_total",
    "Total external service calls",
    ["service", "endpoint", "status"],
    registry=registry
)

external_service_duration_seconds = Histogram(
    "external_service_duration_seconds",
    "External service call duration in seconds",
    ["service", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=registry
)

# Database metrics
db_operations_total = Counter(
    "db_operations_total",
    "Total database operations",
    ["operation", "collection", "status"],
    registry=registry
)

db_operation_duration_seconds = Histogram(
    "db_operation_duration_seconds",
    "Database operation duration in seconds",
    ["operation", "collection"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    registry=registry
)

# Error metrics
errors_total = Counter(
    "errors_total",
    "Total errors",
    ["type", "service"],
    registry=registry
)

# Response time summary
response_time_summary = Summary(
    "response_time_seconds",
    "Response time in seconds",
    ["endpoint"],
    registry=registry
)

def collect_system_metrics():
    """Collect system metrics every 5 seconds"""
    # Set process start time once
    process_start_time.labels(service="order_service").set(time.time())
    while True:
        try:
            cpu_percent.labels(service="order_service").set(psutil.cpu_percent(interval=0.1))
            memory_used.labels(service="order_service").set(psutil.virtual_memory().used / 1024 / 1024)
        except Exception as e:
            print(f"Error collecting system metrics: {e}")
        time.sleep(5)

def start_metrics_server():
    """Start the Prometheus metrics server"""
    # Start system metrics collection
    threading.Thread(target=collect_system_metrics, daemon=True).start()
    # Start HTTP server for metrics endpoint with custom registry
    start_http_server(8004, registry=registry)
    print("✅ Order Service metrics server started on port 8004")

# Utility functions for metrics
def record_http_request(method: str, endpoint: str, status: int, duration: float):
    """Record HTTP request metrics"""
    http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
    response_time_summary.labels(endpoint=endpoint).observe(duration)

def record_order_operation(operation: str, status: str):
    """Record order operation metrics"""
    order_operations_total.labels(operation=operation, status=status).inc()

def record_external_service_call(service: str, endpoint: str, status: str, duration: float):
    """Record external service call metrics"""
    external_service_calls_total.labels(service=service, endpoint=endpoint, status=status).inc()
    external_service_duration_seconds.labels(service=service, endpoint=endpoint).observe(duration)

def record_db_operation(operation: str, collection: str, status: str, duration: float):
    """Record database operation metrics"""
    db_operations_total.labels(operation=operation, collection=collection, status=status).inc()
    db_operation_duration_seconds.labels(operation=operation, collection=collection).observe(duration)

def record_error(error_type: str, service: str = "order_service"):
    """Record error metrics"""
    errors_total.labels(type=error_type, service=service).inc()

def update_orders_count(count: int):
    """Update total orders count"""
    orders_total.set(count)

def record_order_value(value: float, currency: str = "USD"):
    """Record order value"""
    order_value_total.labels(currency=currency).inc(value)
