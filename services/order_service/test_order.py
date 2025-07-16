import requests

base = "http://localhost:8000"

# Step 1: Create order
resp = requests.post(f"{base}/order", json={
    "user_id": "699",
    "item_id": "item_test",
    "quantity": 7
})
print("Create Order Response:", resp.json())

# Step 2: Get order
order_id = resp.json()["order_id"]
resp = requests.get(f"{base}/order/{order_id}")
print("Get Order Response:", resp.json())
