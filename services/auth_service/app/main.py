from fastapi import FastAPI, Request, HTTPException
from app.routes import router
from app.middleware import ResponseTimeLoggerMiddleware
from app.metrics import start_metrics_server
import logging
import json
from datetime import datetime
from fastapi.exception_handlers import http_exception_handler

app = FastAPI()

# Register middleware for logging response time
app.add_middleware(ResponseTimeLoggerMiddleware)

# Include your API routes
app.include_router(router)

# Start Prometheus metrics background collector
start_metrics_server()

# Optional health check
@app.get("/ping")
async def ping():
    return {"message": "auth service is alive"}

@app.exception_handler(HTTPException)
async def http_exception_handler_custom(request: Request, exc: HTTPException):
    log_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": "ERROR",
        "service": "auth_service",
        "method": request.method,
        "path": request.url.path,
        "status_code": exc.status_code,
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "request_id": request.headers.get("x-request-id", "unknown"),
        "message": f"HTTPException: {exc.detail}"
    }
    logging.error(json.dumps(log_data))
    for handler in logging.getLogger().handlers:
        handler.flush()
    return await http_exception_handler(request, exc)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": "ERROR",
        "service": "auth_service",
        "method": request.method,
        "path": request.url.path,
        "status_code": 500,
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "request_id": request.headers.get("x-request-id", "unknown"),
        "message": f"Unhandled Exception: {str(exc)}"
    }
    logging.error(json.dumps(log_data))
    for handler in logging.getLogger().handlers:
        handler.flush()
    raise exc
