from pymongo import MongoClient
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json

# === MongoDB Config ===
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_USER = os.getenv("MONGO_USER", "admin")
MONGO_PASS = os.getenv("MONGO_PASS", "secret")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")
DB_NAME = os.getenv("DB_NAME", "monitoring")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "metrics")

# === Mongo Connection ===
mongo_uri = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
client = MongoClient(mongo_uri)
collection = client[DB_NAME][COLLECTION_NAME]

# === Define expected metrics ===
REQUIRED_METRICS = {"cpu_percent", "memory_used_mb", "http_requests_total", "errors_total"}

# === Group documents by (timestamp, service) ===
grouped = defaultdict(lambda: {"metrics": {}, "timestamp": None})

cursor = collection.find({}, no_cursor_timeout=True).sort("timestamp", 1)

for doc in cursor:
    ts = doc.get("timestamp")
    service = doc.get("service_name")
    metric = doc.get("metric_type")
    value = doc.get("value")

    if not (ts and service and metric and value is not None):
        continue

    key = (ts.isoformat(), service)
    grouped[key]["metrics"][metric] = value
    grouped[key]["timestamp"] = ts
    grouped[key]["service"] = service

# === Write to log ===
log_path = Path("/forecast/exportedMetrics.log")
log_path.parent.mkdir(parents=True, exist_ok=True)

written = 0
with open(log_path, "w") as f:
    for (ts_iso, service), data in grouped.items():
        metrics = data["metrics"]
        if not REQUIRED_METRICS.issubset(metrics.keys()):
            continue  # skip if any required metric is missing

        # Convert to IST
        ist_time = data["timestamp"].replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))
        formatted_time = ist_time.strftime("%Y-%m-%d %H:%M:%S")

        entry = {
            "timestamp": formatted_time,
            "service": service,
            **{metric: metrics[metric] for metric in REQUIRED_METRICS}
        }

        f.write(json.dumps(entry) + "\n")
        written += 1

print(f"✅ Exported {written} complete entries to {log_path.resolve()}")