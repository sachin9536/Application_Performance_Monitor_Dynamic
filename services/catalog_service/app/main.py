from fastapi import FastAPI, Request, HTTPException
from .routes import router
from .middleware import LoggingMiddleware
from .metrics import start_metrics_server
import threading
import logging
import json
from datetime import datetime
from fastapi.exception_handlers import http_exception_handler

app = FastAPI(title="Catalog Service", version="1.0.0")

# Add middleware
app.add_middleware(LoggingMiddleware)

# Include routes
app.include_router(router, prefix="/api/v1")

@app.get("/ping")
async def ping():
    return {"status": "healthy", "service": "catalog_service"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "catalog_service",
        "version": "1.0.0",
        "endpoints": [
            "/api/v1/all_products",
            "/api/v1/product",
            "/api/v1/product_by_id",
            "/api/v1/add_product",
            "/api/v1/update_stock"
        ]
    }

# Start metrics server in background
@app.on_event("startup")
async def startup_event():
    # Start metrics server in a separate thread
    metrics_thread = threading.Thread(target=start_metrics_server, daemon=True)
    metrics_thread.start()
    print("🚀 Catalog Service started with enhanced metrics and logging")

@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 Catalog Service shutting down")

@app.exception_handler(HTTPException)
async def http_exception_handler_custom(request: Request, exc: HTTPException):
    log_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": "ERROR",
        "service": "catalog_service",
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
        "service": "catalog_service",
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