import time
import logging
import json
import os
from datetime import datetime
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Histogram
from .metrics import record_http_request, record_error

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure structured logging to shared log file
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.FileHandler("logs/metrics.log", mode='a'), logging.StreamHandler()]
)

# Prometheus histogram for response time in milliseconds
RESPONSE_TIME_HISTOGRAM = Histogram(
    "response_time_ms",
    "Response time per endpoint in milliseconds",
    ["method", "endpoint", "status_code"],
    buckets=[10, 25, 50, 100, 200, 300, 400, 500, 1000, 2000, 5000]
)

class ResponseTimeLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        # Extract request details
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Process request
        try:
            response = await call_next(request)
            process_time_ms = (time.time() - start_time) * 1000
            
            # Record metrics (always)
            RESPONSE_TIME_HISTOGRAM.labels(
                method=method,
                endpoint=path,
                status_code=response.status_code
            ).observe(process_time_ms)
            
            # Record HTTP request metric (always)
            record_http_request(method, path, response.status_code, time.time() - start_time)
            
            # SELECTIVE LOGGING: Only log errors, warnings, and important events
            should_log = False
            log_level = "INFO"
            
            # Always log errors (4xx, 5xx)
            if response.status_code >= 400:
                should_log = True
                log_level = "ERROR"
                log_data = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "level": log_level,
                    "service": "auth_service",
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "latency_ms": round(process_time_ms, 2),
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "request_id": request.headers.get("x-request-id", "unknown"),
                    "message": f"Request failed with status {response.status_code}"
                }
            
            # Log slow requests (>500ms)
            elif process_time_ms > 500:
                should_log = True
                log_level = "WARNING"
                log_data = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "level": log_level,
                    "service": "auth_service",
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "latency_ms": round(process_time_ms, 2),
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "request_id": request.headers.get("x-request-id", "unknown"),
                    "message": f"Slow request detected: {process_time_ms:.2f}ms"
                }
            
            # Log important business events (login, register)
            elif path in ["/signin", "/register"]:
                should_log = True
                log_level = "INFO"
                log_data = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "level": log_level,
                    "service": "auth_service",
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "latency_ms": round(process_time_ms, 2),
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "request_id": request.headers.get("x-request-id", "unknown"),
                    "message": f"Business event: {path} - Status {response.status_code}"
                }
            
            # Log if needed
            if should_log:
                if log_level == "ERROR":
                    logging.error(json.dumps(log_data))
                elif log_level == "WARNING":
                    logging.warning(json.dumps(log_data))
                else:
                    logging.info(json.dumps(log_data))
                
                # Flush handlers
                for handler in logging.getLogger().handlers:
                    handler.flush()
            
            # Add response headers for tracing
            response.headers["X-Response-Time"] = f"{process_time_ms:.2f}ms"
            response.headers["X-Request-ID"] = request.headers.get("x-request-id", "unknown")
            return response
            
        except Exception as e:
            process_time_ms = (time.time() - start_time) * 1000
            
            # Record error metrics
            record_error("request_failed", "auth_service")
            record_http_request(method, path, 500, time.time() - start_time)
            
            # Always log exceptions
            log_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "ERROR",
                "service": "auth_service",
                "method": method,
                "path": path,
                "status_code": 500,
                "latency_ms": round(process_time_ms, 2),
                "client_ip": client_ip,
                "user_agent": user_agent,
                "request_id": request.headers.get("x-request-id", "unknown"),
                "error": str(e),
                "error_type": type(e).__name__,
                "message": f"Request failed: {str(e)}"
            }
            logging.error(json.dumps(log_data))
            for handler in logging.getLogger().handlers:
                handler.flush()
            raise

        # Optional: Save to MongoDB
        # metrics_db.service_metrics.insert_one(log_data)