#!/usr/bin/env python3
"""
Debug script to test authentication and service registration
"""
import requests
import json
import os

# Configuration
BASE_URL = "http://localhost:8000"
TEST_EMAIL = "x@gmail.com"
TEST_PASSWORD = "123456"  # Replace with your actual password

def test_login():
    """Test login and get JWT token"""
    print("=== Testing Login ===")
    login_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    try:
        response = requests.post(f"{BASE_URL}/login", json=login_data)
        print(f"Login Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                print(f"✅ Login successful! Token: {token[:50]}...")
                return token
            else:
                print("❌ No access_token in response")
                return None
        else:
            print(f"❌ Login failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def test_registered_services(token):
    """Test getting registered services with JWT"""
    print("\n=== Testing Registered Services ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/api/registered_services", headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            services = data.get("registered_services", [])
            print(f"✅ Found {len(services)} registered services")
            for service in services:
                print(f"  - {service.get('name')} ({service.get('url')})")
            return services
        else:
            print(f"❌ Failed to get services: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error getting services: {e}")
        return []

def test_all_registered_services():
    """Test getting all registered services (no auth required)"""
    print("\n=== Testing All Registered Services (No Auth) ===")
    
    try:
        response = requests.get(f"{BASE_URL}/api/all_registered_services")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            services = data.get("registered_services", [])
            print(f"✅ Found {len(services)} total registered services")
            for service in services:
                print(f"  - {service.get('name')} ({service.get('url')}) - Owner: {service.get('owner')}")
            return services
        else:
            print(f"❌ Failed to get all services: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error getting all services: {e}")
        return []

def test_health():
    """Test health endpoint"""
    print("\n=== Testing Health Endpoint ===")
    
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {e}")

def register_test_service(token):
    """Register a test service"""
    print("\n=== Registering Test Service ===")
    headers = {"Authorization": f"Bearer {token}"}
    service_data = {
        "name": "test_service",
        "url": "http://localhost:3001"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/registered_services", json=service_data, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Test service registered successfully")
        else:
            print(f"❌ Failed to register test service: {response.status_code}")
    except Exception as e:
        print(f"❌ Error registering test service: {e}")

def main():
    print("🔍 AppVital Authentication & Service Registration Debug")
    print("=" * 60)
    
    # Test health first
    test_health()
    
    # Test login
    token = test_login()
    if not token:
        print("\n❌ Cannot proceed without valid token")
        return
    
    # Test getting all services (no auth)
    all_services = test_all_registered_services()
    
    # Test getting user's services (with auth)
    user_services = test_registered_services(token)
    
    # If no services, try to register one
    if not user_services:
        print("\n📝 No services found for user. Attempting to register a test service...")
        register_test_service(token)
        
        # Test again
        user_services = test_registered_services(token)
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"  - Total services in system: {len(all_services)}")
    print(f"  - Services for user '{TEST_EMAIL}': {len(user_services)}")
    
    if user_services:
        print("✅ User has registered services - Metrics tab should work!")
    else:
        print("❌ User has no registered services - Register some services first")

if __name__ == "__main__":
    main() 