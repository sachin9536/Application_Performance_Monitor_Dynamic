#!/usr/bin/env python3
"""
Simple script to register demo services for testing
"""
import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
TEST_EMAIL = "x@gmail.com"
TEST_PASSWORD = "123456"  # Replace with your actual password

# Demo services to register
DEMO_SERVICES = [
    {
        "name": "demo_api_service",
        "url": "http://localhost:3001"
    },
    {
        "name": "demo_web_service", 
        "url": "http://localhost:3002"
    },
    {
        "name": "demo_db_service",
        "url": "http://localhost:3003"
    }
]

def login():
    """Login and get JWT token"""
    login_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    try:
        response = requests.post(f"{BASE_URL}/login", json=login_data)
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def register_service(token, service_data):
    """Register a service"""
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(f"{BASE_URL}/api/registered_services", json=service_data, headers=headers)
        if response.status_code == 200:
            print(f"✅ Registered: {service_data['name']}")
            return True
        else:
            print(f"❌ Failed to register {service_data['name']}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error registering {service_data['name']}: {e}")
        return False

def main():
    print("🚀 Registering Demo Services for Testing")
    print("=" * 50)
    
    # Login
    print("🔐 Logging in...")
    token = login()
    if not token:
        print("❌ Cannot proceed without valid token")
        return
    
    print("✅ Login successful!")
    
    # Register services
    print("\n📝 Registering demo services...")
    success_count = 0
    
    for service in DEMO_SERVICES:
        if register_service(token, service):
            success_count += 1
    
    print(f"\n📊 Summary: {success_count}/{len(DEMO_SERVICES)} services registered successfully")
    
    if success_count > 0:
        print("✅ Demo services registered! You can now test the Metrics tab.")
        print("💡 Note: These are demo services - they won't have real metrics until you start actual services on those ports.")
    else:
        print("❌ No services were registered. Check the error messages above.")

if __name__ == "__main__":
    main() 