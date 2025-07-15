from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from utils.auth import verify_token
import os
import httpx
import time
from bson import ObjectId
from .metrics import (
    record_http_request, record_order_operation, record_external_service_call,
    record_db_operation, record_error, update_orders_count, record_order_value
)
import logging
import json

router = APIRouter()

# DB Setup
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client.order_service
orders_collection = db.orders

try:
    client.admin.command('ping')
    print("✅ MongoDB connection successful")
except Exception as e:
    print("❌ MongoDB connection failed:", e)
    record_error("db_connection_failed")


# Models
class OrderCreateModel(BaseModel):
    item_id: str
    quantity: int

CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://catalog_service:8000")  # Adjust port & host in Docker

@router.post("/order")
async def create_order(
    data: OrderCreateModel,
    request: Request,
    user=Depends(verify_token)
):
    start_time = time.time()
    
    try:
        # 1. Check stock from catalog_service by ID
        token = request.headers.get("authorization")
        headers = {"Authorization": token} if token else {}
        
        catalog_start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CATALOG_SERVICE_URL}/product_by_id",
                params={"id": data.item_id},
                headers=headers
            )
            resp.raise_for_status()
            product = resp.json()
        catalog_duration = time.time() - catalog_start
        
        record_external_service_call("catalog", "/product_by_id", "success", catalog_duration)
        
    except httpx.HTTPStatusError:
        record_external_service_call("catalog", "/product_by_id", "failure", time.time() - catalog_start)
        record_http_request("POST", "/order", 404, time.time() - start_time)
        record_order_operation("create", "failure")
        record_error("product_not_found")
        # Log order creation failure
        logging.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "WARNING",
            "service": "order_service",
            "event": "order_creation_failed",
            "user_email": user["email"],
            "item_id": data.item_id,
            "quantity": data.quantity,
            "message": "Order creation failed: Product not found"
        }))
        raise HTTPException(status_code=404, detail="Product not found")
    except Exception as e:
        record_external_service_call("catalog", "/product_by_id", "failure", time.time() - catalog_start)
        record_http_request("POST", "/order", 500, time.time() - start_time)
        record_order_operation("create", "failure")
        record_error("catalog_service_error")
        # Log order creation error
        logging.error(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "order_service",
            "event": "order_creation_error",
            "user_email": user["email"],
            "item_id": data.item_id,
            "quantity": data.quantity,
            "error": str(e),
            "message": f"Order creation failed: {str(e)}"
        }))
        raise HTTPException(status_code=500, detail="Catalog service error")

    # 2. Check stock
    if product["stock"] < data.quantity:
        record_http_request("POST", "/order", 400, time.time() - start_time)
        record_order_operation("create", "failure")
        record_error("insufficient_stock")
        # Log insufficient stock
        logging.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "WARNING",
            "service": "order_service",
            "event": "order_creation_failed",
            "user_email": user["email"],
            "item_id": data.item_id,
            "quantity": data.quantity,
            "message": "Order creation failed: Insufficient stock"
        }))
        raise HTTPException(status_code=400, detail="Insufficient stock")

    # 3. Create the order
    order = {
        "user_email": user["email"],
        "item_id": data.item_id,
        "quantity": data.quantity,
        "created_at": datetime.now(timezone.utc),
        "status": "placed"
    }

    try:
        db_start = time.time()
        result = await orders_collection.insert_one(order)
        db_duration = time.time() - db_start
        record_db_operation("insert", "orders", "success", db_duration)
        
        # Update orders count
        count = await orders_collection.count_documents({})
        update_orders_count(count)
        
        # Record order value (assuming $10 per unit for demo)
        order_value = data.quantity * 10
        record_order_value(order_value)
        
        # Log order creation success
        logging.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "order_service",
            "event": "order_created",
            "user_email": user["email"],
            "item_id": data.item_id,
            "quantity": data.quantity,
            "order_id": str(result.inserted_id),
            "message": "Order created successfully"
        }))
        
    except Exception as e:
        record_db_operation("insert", "orders", "failure", time.time() - db_start)
        record_http_request("POST", "/order", 500, time.time() - start_time)
        record_order_operation("create", "failure")
        record_error("order_creation_failed")
        # Log order creation error
        logging.error(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "order_service",
            "event": "order_creation_error",
            "user_email": user["email"],
            "item_id": data.item_id,
            "quantity": data.quantity,
            "error": str(e),
            "message": f"Order creation failed: {str(e)}"
        }))
        raise HTTPException(status_code=500, detail="Failed to create order")

    # 4. Decrease stock in catalog_service
    try:
        stock_start = time.time()
        async with httpx.AsyncClient() as client:
            await client.post(f"{CATALOG_SERVICE_URL}/update_stock", json={
                "product_id": data.item_id,
                "quantity": data.quantity
            })
        stock_duration = time.time() - stock_start
        record_external_service_call("catalog", "/update_stock", "success", stock_duration)
        
    except Exception as e:
        # Rollback order
        await orders_collection.delete_one({"_id": result.inserted_id})
        record_external_service_call("catalog", "/update_stock", "failure", time.time() - stock_start)
        record_http_request("POST", "/order", 500, time.time() - start_time)
        record_order_operation("create", "failure")
        record_error("stock_update_failed")
        # Log stock update failure
        logging.error(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "order_service",
            "event": "stock_update_failed",
            "user_email": user["email"],
            "item_id": data.item_id,
            "quantity": data.quantity,
            "order_id": str(result.inserted_id),
            "error": str(e),
            "message": f"Stock update failed: {str(e)}"
        }))
        raise HTTPException(status_code=500, detail="Failed to update stock")

    duration = time.time() - start_time
    record_http_request("POST", "/order", 200, duration)
    record_order_operation("create", "success")
    
    return {"status": "success", "order_id": str(result.inserted_id)}



@router.get("/orders")
async def get_user_orders(user=Depends(verify_token)):  # ✅ No email param
    start_time = time.time()
    
    try:
        db_start = time.time()
        cursor = orders_collection.find({"user_email": user["email"]})
        orders = []
        async for order in cursor:
            order["_id"] = str(order["_id"])
            orders.append(order)
        db_duration = time.time() - db_start
        record_db_operation("find", "orders", "success", db_duration)
        
        duration = time.time() - start_time
        record_http_request("GET", "/orders", 200, duration)
        record_order_operation("read", "success")
        
        # Log order fetch success
        logging.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "order_service",
            "event": "orders_fetched",
            "user_email": user["email"],
            "orders_count": len(orders),
            "message": "Fetched user orders successfully"
        }))
        
        return {"orders": orders}
        
    except Exception as e:
        record_error("orders_fetch_failed")
        record_http_request("GET", "/orders", 500, time.time() - start_time)
        record_order_operation("read", "failure")
        # Log order fetch error
        logging.error(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "order_service",
            "event": "orders_fetch_error",
            "user_email": user["email"],
            "error": str(e),
            "message": f"Failed to fetch user orders: {str(e)}"
        }))
        raise HTTPException(status_code=500, detail="Failed to fetch orders")