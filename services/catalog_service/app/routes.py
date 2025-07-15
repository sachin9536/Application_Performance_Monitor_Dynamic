from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from fastapi import Query
import os
from bson import ObjectId
import sys
import time
import logging
import json
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from motor.motor_asyncio import AsyncIOMotorClient
from utils.auth import verify_token
from .metrics import (
    record_http_request, record_product_operation, record_stock_update,
    record_db_operation, record_error, update_products_count
)

router = APIRouter()

MONGO_URI = os.getenv("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
db = client.catalog_service
products_collection = db.products

class ProductResponseModel(BaseModel):
    name: str
    description: str
    stock: int

class ProductCreateModel(BaseModel):
    name: str
    description: str
    stock: int

class StockUpdateModel(BaseModel):
    product_id: str
    quantity: int

@router.get("/product", response_model=list[ProductResponseModel])
async def get_product_by_name(
    name: str = Query(...),
    user=Depends(verify_token)
):
    start_time = time.time()
    
    try:
        db_start = time.time()
        cursor = products_collection.find({"name": {"$regex": name, "$options": "i"}})
        products = []
        async for product in cursor:
            products.append({
                "_id": str(product["_id"]),
                "name": product["name"],
                "description": product["description"],
                "stock": product["stock"]
            })
        db_duration = time.time() - db_start
        record_db_operation("find", "products", "success", db_duration)
        
        if not products:
            record_http_request("GET", "/product", 404, time.time() - start_time)
            record_product_operation("read", "failure")
            record_error("product_not_found")
            raise HTTPException(status_code=404, detail="No products found")
        
        duration = time.time() - start_time
        record_http_request("GET", "/product", 200, duration)
        record_product_operation("read", "success")
        
        return products
        
    except HTTPException:
        raise
    except Exception as e:
        record_error("product_search_failed")
        record_http_request("GET", "/product", 500, time.time() - start_time)
        record_product_operation("read", "failure")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/update_stock")
async def update_stock(data: StockUpdateModel, user=Depends(verify_token)):
    start_time = time.time()
    
    try:
        db_start = time.time()
        result = await products_collection.update_one(
            {"_id": ObjectId(data.product_id), "stock": {"$gte": data.quantity}},
            {"$inc": {"stock": -data.quantity}}
        )
        db_duration = time.time() - db_start
        record_db_operation("update", "products", "success", db_duration)
        
        if result.modified_count == 0:
            record_http_request("POST", "/update_stock", 400, time.time() - start_time)
            record_stock_update("failure")
            record_error("insufficient_stock")
            # Log stock update failure
            logging.info(json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "WARNING",
                "service": "catalog_service",
                "event": "stock_update_failed",
                "product_id": data.product_id,
                "quantity": data.quantity,
                "message": "Stock update failed: Insufficient stock or product not found"
            }))
            raise HTTPException(status_code=400, detail="Insufficient stock or product not found")
        
        duration = time.time() - start_time
        record_http_request("POST", "/update_stock", 200, duration)
        record_stock_update("success")
        # Log stock update success
        logging.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "catalog_service",
            "event": "stock_updated",
            "product_id": data.product_id,
            "quantity": data.quantity,
            "message": "Stock updated successfully"
        }))
        
        return {"status": "stock updated"}
        
    except HTTPException:
        raise
    except Exception as e:
        record_error("stock_update_failed")
        record_http_request("POST", "/update_stock", 500, time.time() - start_time)
        record_stock_update("failure")
        # Log stock update error
        logging.error(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "catalog_service",
            "event": "stock_update_error",
            "product_id": data.product_id,
            "quantity": data.quantity,
            "error": str(e),
            "message": f"Failed to update stock: {str(e)}"
        }))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/add_product")
async def add_product(data: ProductCreateModel, user=Depends(verify_token)):
    start_time = time.time()
    
    try:
        product = {
            "name": data.name,
            "description": data.description,
            "stock": data.stock
        }
        
        db_start = time.time()
        result = await products_collection.insert_one(product)
        db_duration = time.time() - db_start
        record_db_operation("insert", "products", "success", db_duration)
        
        # Update products count
        count = await products_collection.count_documents({})
        update_products_count(count)
        
        duration = time.time() - start_time
        record_http_request("POST", "/add_product", 200, duration)
        record_product_operation("create", "success")
        # Log product creation success
        logging.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "catalog_service",
            "event": "product_created",
            "name": data.name,
            "description": data.description,
            "stock": data.stock,
            "product_id": str(result.inserted_id),
            "message": "Product added successfully"
        }))
        
        return {
            "status": "success",
            "product_id": str(result.inserted_id),
            "msg": "Product added successfully"
        }
        
    except Exception as e:
        record_error("product_creation_failed")
        record_http_request("POST", "/add_product", 500, time.time() - start_time)
        record_product_operation("create", "failure")
        # Log product creation error
        logging.error(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "catalog_service",
            "event": "product_creation_error",
            "name": data.name,
            "description": data.description,
            "stock": data.stock,
            "error": str(e),
            "message": f"Failed to add product: {str(e)}"
        }))
        raise HTTPException(status_code=500, detail="Failed to add product")

@router.get("/all_products")
async def get_all_products(user=Depends(verify_token)):
    start_time = time.time()
    
    try:
        db_start = time.time()
        products = []
        async for product in products_collection.find():
            products.append({
                "_id": str(product["_id"]),
                "name": product["name"],
                "description": product["description"],
                "stock": product["stock"]
            })
        db_duration = time.time() - db_start
        record_db_operation("find", "products", "success", db_duration)
        
        if not products:
            record_http_request("GET", "/all_products", 404, time.time() - start_time)
            record_product_operation("read", "failure")
            record_error("no_products_found")
            # Log product fetch failure
            logging.info(json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "WARNING",
                "service": "catalog_service",
                "event": "products_fetch_failed",
                "message": "No products found"
            }))
            raise HTTPException(status_code=404, detail="No products found")
        
        duration = time.time() - start_time
        record_http_request("GET", "/all_products", 200, duration)
        record_product_operation("read", "success")
        # Log product fetch success
        logging.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "catalog_service",
            "event": "products_fetched",
            "count": len(products),
            "message": "Fetched all products successfully"
        }))
        
        return products
        
    except HTTPException:
        raise
    except Exception as e:
        record_error("products_fetch_failed")
        record_http_request("GET", "/all_products", 500, time.time() - start_time)
        record_product_operation("read", "failure")
        # Log product fetch error
        logging.error(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "catalog_service",
            "event": "products_fetch_error",
            "error": str(e),
            "message": f"Failed to fetch products: {str(e)}"
        }))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/product_by_id")
async def get_product_by_id(id: str = Query(...), user=Depends(verify_token)):
    start_time = time.time()
    
    try:
        db_start = time.time()
        product = await products_collection.find_one({"_id": ObjectId(id)})
        db_duration = time.time() - db_start
        record_db_operation("find", "products", "success", db_duration)
        
        if not product:
            record_http_request("GET", "/product_by_id", 404, time.time() - start_time)
            record_product_operation("read", "failure")
            record_error("product_not_found")
            raise HTTPException(status_code=404, detail="Product not found")
        
        duration = time.time() - start_time
        record_http_request("GET", "/product_by_id", 200, duration)
        record_product_operation("read", "success")
        
        return {
            "_id": str(product["_id"]),
            "name": product["name"],
            "description": product["description"],
            "stock": product["stock"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        record_error("product_fetch_failed")
        record_http_request("GET", "/product_by_id", 500, time.time() - start_time)
        record_product_operation("read", "failure")
        raise HTTPException(status_code=500, detail="Internal server error")
