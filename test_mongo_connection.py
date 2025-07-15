#!/usr/bin/env python3
"""
Test MongoDB connection script to debug connection issues
"""
import os
import sys
import time
import pymongo
from datetime import datetime

def test_mongo_connection():
    """Test MongoDB connection with various configurations"""
    
    # Test different connection strings
    connection_strings = [
        "mongodb://admin:secret@mongodb:27017",
        "mongodb://admin:secret@localhost:27017",
        "mongodb://mongodb:27017",
        "mongodb://localhost:27017"
    ]
    
    print(f"[{datetime.now()}] Testing MongoDB connections...")
    
    for i, uri in enumerate(connection_strings, 1):
        print(f"\n[{datetime.now()}] Test {i}: {uri}")
        try:
            # Try to connect with a short timeout
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
            
            # Test the connection
            client.admin.command('ping')
            print(f"✅ SUCCESS: Connected to MongoDB using {uri}")
            
            # Get server info
            info = client.server_info()
            print(f"   Server version: {info.get('version', 'unknown')}")
            print(f"   Server uptime: {info.get('uptime', 'unknown')} seconds")
            
            client.close()
            return True
            
        except pymongo.errors.ServerSelectionTimeoutError as e:
            print(f"❌ TIMEOUT: Could not connect to MongoDB using {uri}")
            print(f"   Error: {e}")
        except pymongo.errors.OperationFailure as e:
            print(f"❌ AUTH ERROR: Authentication failed for {uri}")
            print(f"   Error: {e}")
        except Exception as e:
            print(f"❌ ERROR: Unexpected error with {uri}")
            print(f"   Error: {e}")
    
    return False

def test_mongo_health():
    """Test MongoDB health check similar to Docker healthcheck"""
    print(f"\n[{datetime.now()}] Testing MongoDB health check...")
    
    try:
        # This is similar to the Docker healthcheck command
        client = pymongo.MongoClient(
            "mongodb://admin:secret@mongodb:27017",
            serverSelectionTimeoutMS=5000
        )
        
        # Test admin command
        result = client.admin.command('ping')
        print(f"✅ Health check passed: {result}")
        
        # Test database operations
        db = client.test
        collection = db.test_collection
        
        # Insert a test document
        doc = {"test": True, "timestamp": datetime.now()}
        result = collection.insert_one(doc)
        print(f"✅ Write test passed: {result.inserted_id}")
        
        # Read the document
        found = collection.find_one({"_id": result.inserted_id})
        print(f"✅ Read test passed: {found is not None}")
        
        # Clean up
        collection.delete_one({"_id": result.inserted_id})
        print(f"✅ Cleanup test passed")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("MongoDB Connection Test Script")
    print("=" * 60)
    
    # Test basic connection
    connection_ok = test_mongo_connection()
    
    if connection_ok:
        # Test health check
        health_ok = test_mongo_health()
        
        if health_ok:
            print(f"\n[{datetime.now()}] ✅ All MongoDB tests passed!")
            sys.exit(0)
        else:
            print(f"\n[{datetime.now()}] ❌ MongoDB health check failed!")
            sys.exit(1)
    else:
        print(f"\n[{datetime.now()}] ❌ MongoDB connection failed!")
        sys.exit(1) 