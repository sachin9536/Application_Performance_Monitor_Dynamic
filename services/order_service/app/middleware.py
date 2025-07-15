import time
import logging
import json
import os
from datetime import datetime
from fastapi import Request, Response
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
logger = logging.getLogger(__name__)

# Prometheus histogram for response time in milliseconds
RESPONSE_TIME_HISTOGRAM = Histogram(
    "response_time_ms",
    "Response time per endpoint in milliseconds",
    ["method", "endpoint"],
    buckets=[50, 100, 200, 300, 400, 500, 1000, 10000]
)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract request details
        method = request.method
        url = str(request.url)
        path = request.url.path
        query_params = dict(request.query_params)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Log request
        request_log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "order_service",
            "event": "request_start",
            "method": method,
            "path": path,
            "query_params": query_params,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "request_id": request.headers.get("x-request-id", "unknown")
        }
        logger.info(json.dumps(request_log))
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            record_http_request(method, path, response.status_code, duration)

            # Log response or error
            response_log = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "service": "order_service",
                "event": "request_complete",
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "client_ip": client_ip,
                "request_id": request.headers.get("x-request-id", "unknown")
            }
            if response.status_code >= 400:
                response_log["level"] = "ERROR"
                response_log["message"] = f"Request failed with status {response.status_code}"
                logger.error(json.dumps(response_log))
                for handler in logger.handlers:
                    handler.flush()
            else:
                response_log["level"] = "INFO"
                response_log["message"] = "Request processed successfully"
                logger.info(json.dumps(response_log))
                for handler in logger.handlers:
                    handler.flush()
            return response
        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time
            
            # Record error metrics
            record_error("request_failed", "order_service")
            record_http_request(method, path, 500, duration)
            
            # Log error
            error_log = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "ERROR",
                "service": "order_service",
                "event": "request_error",
                "method": method,
                "path": path,
                "error": str(e),
                "duration_ms": round(duration * 1000, 2),
                "client_ip": client_ip,
                "request_id": request.headers.get("x-request-id", "unknown")
            }
            logger.error(json.dumps(error_log))
            for handler in logger.handlers:
                handler.flush()
            raise
