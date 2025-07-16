from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
import bcrypt
import os
import asyncio
import time
from jose import jwt
from .metrics import (
    record_http_request, record_auth_attempt, record_db_operation, 
    record_jwt_operation, record_error, user_registrations_total
)
import logging
import json

JWT_SECRET = os.getenv("JWT_SECRET", "mysecretkey")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 60

router = APIRouter()

# Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
db = client.auth_service
users_collection = db.user_metrics

try:
    client.admin.command('ping')
    print("✅ MongoDB connection successful")
except Exception as e:
    print("❌ MongoDB connection failed:", e)
    record_error("db_connection_failed")

db = client.auth_service
users_collection = db.user_metrics

async def hash_password(password: str) -> bytes:
    return await asyncio.to_thread(bcrypt.hashpw, password.encode('utf-8'), bcrypt.gensalt())

async def verify_password(password: str, hashed: bytes) -> bool:
    return await asyncio.to_thread(bcrypt.checkpw, password.encode('utf-8'), hashed)

# Input schemas
class RegisterModel(BaseModel):
    email: EmailStr
    password: str

class SignInModel(BaseModel):
    email: EmailStr
    password: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRY_MINUTES)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    record_jwt_operation("issue")
    return token

@router.post("/register")
async def register_user(data: RegisterModel):
    start_time = time.time()
    try:
        # Check if user exists
        existing = await users_collection.find_one({"email": data.email})
        if existing:
            record_http_request("POST", "/register", 400, time.time() - start_time)
            record_auth_attempt("register", "failure")
            record_error("user_already_exists")
            # Log registration failure
            logging.info(json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "WARNING",
                "service": "auth_service",
                "event": "user_registration_failed",
                "email": data.email,
                "message": "Registration failed: Email already registered"
            }))
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash password
        hashed_pw = await hash_password(data.password)

        # Create user
        user_data = {
            "email": data.email,
            "passwordHash": hashed_pw,
            "sessionCount": 0,
            "createdAt": datetime.now(timezone.utc),
            "lastLoginAt": None
        }
        db_start = time.time()
        result = await users_collection.insert_one(user_data)
        db_duration = time.time() - db_start
        record_db_operation("insert", "user_metrics", "success", db_duration)
        user_registrations_total.inc()
        duration = time.time() - start_time
        record_http_request("POST", "/register", 200, duration)
        record_auth_attempt("register", "success")
        # Log registration success
        logging.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "auth_service",
            "event": "user_registered",
            "email": data.email,
            "message": "User registered successfully"
        }))
        return {"status": "success", "msg": "User registered"}
    except HTTPException:
        raise
    except Exception as e:
        record_error("registration_failed")
        record_http_request("POST", "/register", 500, time.time() - start_time)
        record_auth_attempt("register", "failure")
        # Log registration error
        logging.error(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "auth_service",
            "event": "user_registration_error",
            "email": data.email,
            "error": str(e),
            "message": f"Registration failed: {str(e)}"
        }))
        raise HTTPException(status_code=500, detail="Database insert failed")

@router.post("/signin")
async def signin_user(data: SignInModel):
    start_time = time.time()
    try:
        db_start = time.time()
        user = await users_collection.find_one({"email": data.email})
        db_duration = time.time() - db_start
        record_db_operation("find", "user_metrics", "success", db_duration)
        if not user:
            record_http_request("POST", "/signin", 401, time.time() - start_time)
            record_auth_attempt("login", "failure")
            record_error("user_not_found")
            # Log login failure
            logging.info(json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "WARNING",
                "service": "auth_service",
                "event": "login_failed",
                "email": data.email,
                "message": "Login failed: User not found"
            }))
            raise HTTPException(status_code=401, detail="Invalid credentials")
        password_ok = await verify_password(data.password, user["passwordHash"])
        if not password_ok:
            record_http_request("POST", "/signin", 401, time.time() - start_time)
            record_auth_attempt("login", "failure")
            record_error("invalid_password")
            # Log login failure
            logging.info(json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "WARNING",
                "service": "auth_service",
                "event": "login_failed",
                "email": data.email,
                "message": "Login failed: Invalid password"
            }))
            raise HTTPException(status_code=401, detail="Invalid credentials")
        update_data = {
            "$inc": {"sessionCount": 1},
            "$set": {"lastLoginAt": datetime.now(timezone.utc)}
        }
        db_start = time.time()
        await users_collection.update_one({"_id": user["_id"]}, update_data)
        db_duration = time.time() - db_start
        record_db_operation("update", "user_metrics", "success", db_duration)
        token = create_access_token({"email": data.email})
        duration = time.time() - start_time
        record_http_request("POST", "/signin", 200, duration)
        record_auth_attempt("login", "success")
        # Log login success
        logging.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "service": "auth_service",
            "event": "login_success",
            "email": data.email,
            "message": "Login successful"
        }))
        return {"status": "success", "access_token": token}
    except HTTPException:
        raise
    except Exception as e:
        record_error("login_failed")
        record_http_request("POST", "/signin", 500, time.time() - start_time)
        record_auth_attempt("login", "failure")
        # Log login error
        logging.error(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "auth_service",
            "event": "login_error",
            "email": data.email,
            "error": str(e),
            "message": f"Login failed: {str(e)}"
        }))
        raise HTTPException(status_code=500, detail="Database update failed")
