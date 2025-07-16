import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Depends, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
import httpx
import time
import re
import os
import json
import hashlib
import jwt
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
import psutil
from dateutil import parser as dateutil_parser
from collections import defaultdict, OrderedDict  # Add this import at the top if not present
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo import MongoClient
import pymongo
from passlib.hash import bcrypt
from urllib.parse import urlparse
import pytz  # Add this import at the top if not present

# Optional: pip install ollama
try:
    import ollama
except ImportError:
    ollama = None

# --- Email Alerting (SendGrid) ---
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
except ImportError:
    SendGridAPIClient = None
    Mail = None

# Add imports for PostgreSQL and MySQL
try:
    import psycopg2
except ImportError:
    psycopg2 = None
try:
    import mysql.connector
except ImportError:
    mysql = None

LOG_PATH = Path("/app/logs/metrics.log")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")

user_service_metrics = {}  # {service_name: {metrics, status, last_scraped, error}}

async def background_user_service_metrics_scraper():
    """Periodically scrape /metrics from user-registered services and cache results."""
    global user_service_metrics, service_uptime_tracker
    while True:
        try:
            # Get all registered services from all users
            all_services = list(services_collection.find({}))
            for svc in all_services:
                name = svc["name"]
                url = svc["url"].rstrip("/")
                owner = svc["owner"]
                metrics_url = f"{url}/metrics"
                current_time = time.time()
                
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(metrics_url)
                    if resp.status_code == 200:
                        # Parse Prometheus metrics text format
                        metrics = parse_prometheus_metrics(resp.text)
                        
                        # Track uptime internally
                        if name not in service_uptime_tracker:
                            service_uptime_tracker[name] = {
                                "first_seen": current_time,
                                "last_healthy": current_time
                            }
                        else:
                            service_uptime_tracker[name]["last_healthy"] = current_time
                        
                        # Calculate uptime from Prometheus process_start_time_seconds
                        uptime = None
                        if "process_start_time_seconds" in metrics:
                            process_start_time = metrics["process_start_time_seconds"]
                            if process_start_time > 0:
                                uptime = (current_time - process_start_time) / 60  # in minutes
                        
                        # Store historical metrics for load forecasting
                        save_metrics_history(name, metrics, current_time)
                        
                        user_service_metrics[name] = {
                            "metrics": metrics,
                            "status": "healthy",
                            "last_scraped": current_time,
                            "error": None,
                            "owner": owner,
                            "url": url,
                            "uptime": uptime
                        }
                    else:
                        user_service_metrics[name] = {
                            "metrics": {},
                            "status": "unhealthy",
                            "last_scraped": current_time,
                            "error": f"Status {resp.status_code}",
                            "owner": owner,
                            "url": url
                        }
                except Exception as e:
                    user_service_metrics[name] = {
                        "metrics": {},
                        "status": "unhealthy",
                        "last_scraped": current_time,
                        "error": str(e),
                        "owner": owner,
                        "url": url
                    }
        except Exception as e:
            print(f"[User Service Metrics Scraper] Error: {e}")
        
        # Save uptime tracker periodically (every 10 minutes)
        if int(time.time()) % 600 == 0:  # Every 10 minutes
            save_uptime_tracker()
            
        # Clean up old metrics data periodically (every 6 hours)
        if int(time.time()) % 21600 == 0:  # Every 6 hours
            cleanup_old_metrics_history(days_to_keep=30)
            
        await asyncio.sleep(30)  # Scrape every 30 seconds

# Add a new function to scrape metrics for a specific user
async def scrape_metrics_for_user(user_email: str):
    """Scrape metrics for a specific user's services."""
    global service_uptime_tracker
    services = get_registered_services_for_user(user_email)
    for svc in services:
        name = svc["name"]
        url = svc["url"].rstrip("/")
        metrics_url = f"{url}/metrics"
        current_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(metrics_url)
            if resp.status_code == 200:
                metrics = parse_prometheus_metrics(resp.text)
                
                # Track uptime internally
                if name not in service_uptime_tracker:
                    service_uptime_tracker[name] = {
                        "first_seen": current_time,
                        "last_healthy": current_time
                    }
                else:
                    service_uptime_tracker[name]["last_healthy"] = current_time
                
                # Calculate uptime from Prometheus process_start_time_seconds
                uptime = None
                if "process_start_time_seconds" in metrics:
                    process_start_time = metrics["process_start_time_seconds"]
                    if process_start_time > 0:
                        uptime = (current_time - process_start_time) / 60  # in minutes
                
                # Store historical metrics for load forecasting
                save_metrics_history(name, metrics, current_time)
                
                user_service_metrics[name] = {
                    "metrics": metrics,
                    "status": "healthy",
                    "last_scraped": current_time,
                    "error": None,
                    "owner": user_email,
                    "url": url,
                    "uptime": uptime
                }
            else:
                user_service_metrics[name] = {
                    "metrics": {},
                    "status": "unhealthy",
                    "last_scraped": current_time,
                    "error": f"Status {resp.status_code}",
                    "owner": user_email,
                    "url": url
                }
        except Exception as e:
            user_service_metrics[name] = {
                "metrics": {},
                "status": "unhealthy",
                "last_scraped": current_time,
                "error": str(e),
                "owner": user_email,
                "url": url
            }

def parse_prometheus_metrics(metrics_text):
    """Parse Prometheus text format into a dict of metric_name: value."""
    metrics = {}
    # Track metrics that need to be summed (like http_requests_total with different labels)
    summable_metrics = {}
    
    for line in metrics_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parts = line.split()
            if len(parts) == 2:
                key, value = parts
                # Check if this is a metric with labels
                if "{" in key:
                    # Extract the base metric name (without labels)
                    base_key = key.split("{")[0]
                    # For metrics that should be summed across all labels
                    if base_key in ["http_requests_total", "errors_total"]:
                        if base_key not in summable_metrics:
                            summable_metrics[base_key] = 0
                        summable_metrics[base_key] += float(value)
                    else:
                        # For other metrics with labels, keep the last value (existing behavior)
                        metrics[base_key] = float(value)
                else:
                    # No labels, store directly
                    metrics[key] = float(value)
        except Exception:
            continue

    # Add the summed metrics to the result
    for metric_name, total_value in summable_metrics.items():
        metrics[metric_name] = total_value

    # --- Compute average latency (seconds) ---
    avg_latency = None
    for prefix in ["http_request_duration_seconds", "total_response_ms"]:
        sum_key = f"{prefix}_sum"
        count_key = f"{prefix}_count"
        if sum_key in metrics and count_key in metrics and metrics[count_key] > 0:
            avg = metrics[sum_key] / metrics[count_key]
            # If using ms, convert to seconds for consistency
            if prefix == "total_response_ms":
                avg = avg / 1000.0
            avg_latency = avg
            break
    if avg_latency is not None:
        metrics["avg_latency"] = avg_latency

    return metrics

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load uptime tracking data on startup
    load_uptime_tracker()
    
    task1 = asyncio.create_task(background_log_scanner())
    task2 = asyncio.create_task(background_user_service_metrics_scraper())
    task3 = asyncio.create_task(background_db_health_checker())
    yield
    task1.cancel()
    task2.cancel()
    task3.cancel()
    
    # Save uptime tracking data on shutdown
    save_uptime_tracker()

app = FastAPI(lifespan=lifespan)

# Add this after creating the app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for parsed log data and detected anomalies
parsed_logs: List[Dict[str, Any]] = []
metrics_summary: Dict[str, Any] = {}
anomaly_cache: List[str] = []
prometheus_metrics: Dict[str, Any] = {}

# --- In-memory cache for root cause analysis ---
root_cause_cache = {}
CACHE_TTL_SECONDS = 120  # 2 minutes

# Track sent anomalies to avoid duplicate emails (in-memory, resets on restart)
sent_anomalies = set()

# --- Service uptime tracking (AppVital internal) ---
service_uptime_tracker = {}  # {service_name: {"first_seen": timestamp, "last_healthy": timestamp}}

def load_uptime_tracker():
    """Load uptime tracking data from file"""
    global service_uptime_tracker
    try:
        uptime_file = Path("/app/data/service_uptime.json")
        if uptime_file.exists():
            with open(uptime_file, "r") as f:
                service_uptime_tracker = json.load(f)
                print(f"Loaded uptime tracking data for {len(service_uptime_tracker)} services")
    except Exception as e:
        print(f"Error loading uptime tracker: {e}")
        service_uptime_tracker = {}

def save_uptime_tracker():
    """Save uptime tracking data to file"""
    try:
        uptime_file = Path("/app/data/service_uptime.json")
        uptime_file.parent.mkdir(exist_ok=True)
        with open(uptime_file, "w") as f:
            json.dump(service_uptime_tracker, f, indent=2)
    except Exception as e:
        print(f"Error saving uptime tracker: {e}")

# --- Authentication Models and Functions ---
class RegisterModel(BaseModel):
    email: EmailStr
    password: str

class LoginModel(BaseModel):
    email: EmailStr
    password: str

# In-memory user storage (in production, use a database)
users_db = {}

def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return hash_password(password) == hashed

def create_access_token(data: dict) -> str:
    """Create a JWT access token"""
    secret = os.getenv("JWT_SECRET", "mysecretkey")
    payload = data.copy()
    payload.update({"exp": datetime.utcnow() + timedelta(hours=24)})
    return jwt.encode(payload, secret, algorithm="HS256")

def send_email_alert(subject, content):
    if not (SENDGRID_API_KEY and ALERT_EMAIL_FROM and ALERT_EMAIL_TO):
        print("[Email Alert] Missing SENDGRID_API_KEY, ALERT_EMAIL_FROM, or ALERT_EMAIL_TO env vars.")
        return
    if not SendGridAPIClient or not Mail:
        print("[Email Alert] SendGrid not installed.")
        return
    message = Mail(
        from_email=ALERT_EMAIL_FROM,
        to_emails=ALERT_EMAIL_TO,
        subject=subject,
        plain_text_content=content,
        html_content=f"<pre>{content}</pre>"
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"[Email Alert] Sent: {subject} (status {response.status_code})")
    except Exception as e:
        print(f"[Email Alert] Failed: {e}")

# --- Enhanced Log Parsing ---
def parse_log_line(line: str) -> Dict[str, Any]:
    """Parse structured and unstructured log lines, normalize level and service, always set message."""
    try:
        if line.strip().startswith('{'):
            data = json.loads(line)
            # Normalize level and service
            if 'level' in data:
                data['level'] = data['level'].upper()
            # Try to infer service if missing or unknown
            if 'service' not in data or not data['service'] or data['service'].lower() == 'unknown':
                msg = data.get('message', '')
                path = data.get('path', '')
                event = data.get('event', '')
                # Improved service inference
                if 'auth_service' in msg or 'auth_service' in event or '/auth' in path or 'auth' in msg.lower():
                    data['service'] = 'auth_service'
                elif 'order_service' in msg or 'order_service' in event or '/order' in path or 'order' in msg.lower():
                    data['service'] = 'order_service'
                elif 'catalog_service' in msg or 'catalog_service' in event or '/catalog' in path or 'catalog' in msg.lower() or 'product' in msg.lower():
                    data['service'] = 'catalog_service'
                elif 'controller' in msg.lower() or 'controller' in event.lower():
                    data['service'] = 'controller'
                else:
                    data['service'] = 'unknown'
            # Always ensure message field exists
            if 'message' not in data or not data['message']:
                # Try to use event or raw
                data['message'] = data.get('event', '') or str(data)
            return data
    except json.JSONDecodeError:
        pass
    # Fallback to regex parsing for unstructured logs
    log_pattern = re.compile(r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) \[(?P<level>\w+)\] (?P<message>.*)")
    match = log_pattern.match(line)
    if match:
        data = match.groupdict()
        data['level'] = data.get('level', '').upper()
        msg = data.get('message', '')
        # Improved service inference
        if 'auth_service' in msg or '/auth' in msg or 'auth' in msg.lower():
            data['service'] = 'auth_service'
        elif 'order_service' in msg or '/order' in msg or 'order' in msg.lower():
            data['service'] = 'order_service'
        elif 'catalog_service' in msg or '/catalog' in msg or 'catalog' in msg.lower() or 'product' in msg.lower():
            data['service'] = 'catalog_service'
        elif 'controller' in msg.lower():
            data['service'] = 'controller'
        else:
            data['service'] = 'unknown'
        # Always ensure message field exists
        if 'message' not in data or not data['message']:
            data['message'] = str(data)
        return data
    # Always set message for raw logs
    return {"raw": line, "timestamp": datetime.now().isoformat(), "level": "INFO", "service": "unknown", "message": line}

def load_logs() -> List[Dict[str, Any]]:
    """Load and parse logs from all service log files"""
    log_files = [
        Path("/app/logs/metrics.log"),  # Main log file (controller)
        Path("/app/logs/auth_service.log"),  # Auth service logs
        Path("/app/logs/catalog_service.log"),  # Catalog service logs
        Path("/app/logs/order_service.log"),  # Order service logs
    ]
    
    logs = []
    for log_file in log_files:
        if not log_file.exists():
            continue
        
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-16', 'latin-1']
            file_content = None
            
            for encoding in encodings:
                try:
                    with log_file.open("r", encoding=encoding) as f:
                        file_content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if file_content is None:
                print(f"Could not read {log_file} with any encoding")
                continue
                
            for line in file_content.split('\n'):
                line = line.strip()
                if line:
                    parsed = parse_log_line(line)
                    if parsed:
                        logs.append(parsed)
                        
        except Exception as e:
            print(f"Error loading logs from {log_file}: {e}")
    
    return logs

# --- Enhanced Metrics Analysis ---
def analyze_logs(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Comprehensive log analysis with industry-standard metrics"""
    stats = {
        "total": len(logs),
        "errors": 0,
        "auth_failures": 0,
        "http_500": 0,
        "order_404": 0,
        "latencies": [],
        "last_10_errors": [],
        "error_types": {},
        "response_codes": {},
        "services": {},
        "time_series": {},
        "performance_metrics": {
            "avg_latency_ms": None,
            "min_latency_ms": None,
            "max_latency_ms": None,
            "p95_latency_ms": None,
            "p99_latency_ms": None,
            "error_rate": 0.0,
            "success_rate": 0.0
        }
    }
    
    # Time-based analysis (fix: each window is exclusive, not cumulative)
    current_time = datetime.now()
    time_windows = {
        "last_1h": current_time - timedelta(hours=1),
        "last_15m": current_time - timedelta(minutes=15),
        "last_5m": current_time - timedelta(minutes=5)
    }
    
    # Prepare time series buckets
    for window_name in time_windows:
        stats["time_series"][window_name] = {"total": 0, "errors": 0}
    
    for log in logs:
        msg = log.get("message", "")
        level = log.get("level", "")
        service = log.get("service", "unknown")
        status_code = log.get("status_code")
        latency = log.get("latency_ms")
        if latency is None:
            latency = log.get("duration_ms")
        timestamp_str = log.get("timestamp", "")
        
        # Service tracking
        if service not in stats["services"]:
            stats["services"][service] = {
                "total_requests": 0,
                "errors": 0,
                "avg_latency": 0,
                "latencies": []
            }
        
        stats["services"][service]["total_requests"] += 1
        
        # Count errors
        if "error" in msg.lower() or level == "ERROR":
            stats["errors"] += 1
            stats["services"][service]["errors"] += 1
            if len(stats["last_10_errors"]) < 10:
                stats["last_10_errors"].append(log)
        
        # Count specific error types
        if "401" in msg or "authentication failed" in msg.lower():
            stats["auth_failures"] += 1
            stats["error_types"]["auth_failure"] = stats["error_types"].get("auth_failure", 0) + 1
        if "500" in msg or (status_code and status_code == 500):
            stats["http_500"] += 1
            stats["error_types"]["http_500"] = stats["error_types"].get("http_500", 0) + 1
        if "404" in msg and "order" in msg.lower():
            stats["order_404"] += 1
            stats["error_types"]["order_404"] = stats["error_types"].get("order_404", 0) + 1
        
        # Latency analysis
        if latency is not None:
            stats["latencies"].append(latency)
            stats["services"][service]["latencies"].append(latency)
        
        # Response code analysis
        if status_code:
            stats["response_codes"][str(status_code)] = stats["response_codes"].get(str(status_code), 0) + 1
        
        # Time series analysis (fix: each window is exclusive)
        try:
            if timestamp_str:
                log_time = dateutil_parser.parse(timestamp_str)
                for window_name, window_start in time_windows.items():
                    # Only count logs within this window (not cumulative)
                    if log_time >= window_start and log_time <= current_time:
                        # For each window, check if log_time is within window's range only
                        # For last_5m: >= now-5m and <= now
                        # For last_15m: >= now-15m and < now-5m
                        # For last_1h: >= now-1h and < now-15m
                        if window_name == "last_5m":
                            if log_time >= current_time - timedelta(minutes=5):
                                stats["time_series"][window_name]["total"] += 1
                                if "error" in msg.lower() or level == "ERROR":
                                    stats["time_series"][window_name]["errors"] += 1
                        elif window_name == "last_15m":
                            if current_time - timedelta(minutes=15) <= log_time < current_time - timedelta(minutes=5):
                                stats["time_series"][window_name]["total"] += 1
                                if "error" in msg.lower() or level == "ERROR":
                                    stats["time_series"][window_name]["errors"] += 1
                        elif window_name == "last_1h":
                            if current_time - timedelta(hours=1) <= log_time < current_time - timedelta(minutes=15):
                                stats["time_series"][window_name]["total"] += 1
                                if "error" in msg.lower() or level == "ERROR":
                                    stats["time_series"][window_name]["errors"] += 1
        except Exception:
            pass
    
    # Calculate performance metrics
    if stats["latencies"]:
        latencies = sorted(stats["latencies"])
        stats["performance_metrics"].update({
            "avg_latency_ms": sum(latencies) / len(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "p95_latency_ms": latencies[int(len(latencies) * 0.95)],
            "p99_latency_ms": latencies[int(len(latencies) * 0.99)]
        })
    
    # Calculate rates
    if stats["total"] > 0:
        stats["performance_metrics"]["error_rate"] = (stats["errors"] / stats["total"]) * 100
        stats["performance_metrics"]["success_rate"] = 100 - stats["performance_metrics"]["error_rate"]
    
    # Calculate service-specific metrics
    for service in stats["services"]:
        service_data = stats["services"][service]
        if service_data["latencies"]:
            service_data["avg_latency"] = sum(service_data["latencies"]) / len(service_data["latencies"])
    
    return stats

async def scrape_prometheus() -> Dict[str, Any]:
    """Enhanced Prometheus metrics scraping with industry-standard queries"""
    metrics = {}
    queries = {
        "up": "up",
        "http_requests_total": "http_requests_total",
        "http_request_duration_seconds": "http_request_duration_seconds",
        "response_time_ms": "response_time_ms",
        "cpu_percent": "cpu_percent",
        "memory_used_mb": "memory_used_mb",
        "auth_attempts_total": "auth_attempts_total",
        "jwt_tokens_issued_total": "jwt_tokens_issued_total",
        "db_operations_total": "db_operations_total",
        "errors_total": "errors_total",
        "process_start_time_seconds": "process_start_time_seconds"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Scrape individual metrics
            for metric_name, query in queries.items():
                try:
                    resp = await client.get(
                        f"{PROMETHEUS_URL}/api/v1/query", 
                        params={"query": query}, 
                        timeout=5
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        metrics[metric_name] = data.get("data", {}).get("result", [])
                    else:
                        metrics[f"{metric_name}_error"] = resp.text
                except Exception as e:
                    metrics[f"{metric_name}_error"] = str(e)
            
            # Get service health status
            resp = await client.get(f"{PROMETHEUS_URL}/api/v1/targets", timeout=5)
            if resp.status_code == 200:
                targets_data = resp.json()
                metrics["targets"] = targets_data.get("data", {}).get("activeTargets", [])
            
            # Get metric metadata
            resp = await client.get(f"{PROMETHEUS_URL}/api/v1/label/__name__/values", timeout=5)
            if resp.status_code == 200:
                metadata = resp.json()
                metrics["available_metrics"] = metadata.get("data", [])
            
    except Exception as e:
        metrics["prometheus_error"] = str(e)
    
    return metrics

# --- Enhanced Anomaly Detection ---
def detect_anomalies(logs: List[Dict[str, Any]]) -> List[str]:
    """Advanced anomaly detection with multiple algorithms"""
    anomalies = []
    
    # Check last 100 logs for anomalies
    recent_logs = logs[-100:] if len(logs) > 100 else logs
    
    # 1. Error rate anomaly
    error_count = sum(1 for log in recent_logs if log.get("level") == "ERROR")
    if error_count > 10:
        anomalies.append(f"High error rate detected: {error_count} errors in last 100 logs")
    
    # 2. HTTP 500 anomaly
    http_500_count = sum(1 for log in recent_logs if "500" in log.get("message", ""))
    if http_500_count > 5:
        anomalies.append(f"Spike in HTTP 500 errors: {http_500_count} in last 100 logs")
    
    # 3. Authentication failures anomaly
    auth_failures = sum(1 for log in recent_logs if "401" in log.get("message", ""))
    if auth_failures > 5:
        anomalies.append(f"Spike in authentication failures: {auth_failures} in last 100 logs")
    
    # 4. Latency anomaly detection
    latencies = []
    for log in recent_logs:
        latency = log.get("latency_ms")
        if latency:
            latencies.append(latency)
    
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        if avg_latency > 1000:  # More than 1 second average
            anomalies.append(f"High average latency detected: {avg_latency:.2f}ms")
        
        # Detect latency spikes (values > 2x average)
        threshold = avg_latency * 2
        spikes = [l for l in latencies if l > threshold]
        if len(spikes) > 3:
            anomalies.append(f"Latency spikes detected: {len(spikes)} requests > {threshold:.2f}ms")
    
    # 5. Service-specific anomalies
    service_errors = {}
    for log in recent_logs:
        service = log.get("service", "unknown")
        if "error" in log.get("message", "").lower() or log.get("level") == "ERROR":
            service_errors[service] = service_errors.get(service, 0) + 1
    
    for service, error_count in service_errors.items():
        if error_count > 3:
            anomalies.append(f"Service {service} has high error rate: {error_count} errors")
    
    # --- Email alert for new anomalies ---
    for anomaly in anomalies:
        if anomaly not in sent_anomalies:
            send_email_alert(
                subject=f"[Health Monitor] Anomaly Detected",
                content=f"Anomaly detected:\n{anomaly}\n\nSee dashboard for details."
            )
            sent_anomalies.add(anomaly)
    return anomalies

# --- Enhanced Ollama Integration with better error handling
async def ask_ollama_for_root_cause_httpx(prompt: str) -> str:
    """Direct HTTP call to Ollama API with comprehensive error handling"""
    url = OLLAMA_URL.rstrip('/')  # Remove trailing slash
    data = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 500
        }
    }
    try:
        print(f"Attempting to connect to Ollama at: {url}/api/generate")
        print(f"Using model: {OLLAMA_MODEL}")
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            # Health check
            try:
                health_resp = await client.get(f"{url}/api/tags", timeout=5.0)
                print(f"Ollama health check status: {health_resp.status_code}")
                if health_resp.status_code != 200:
                    return f"Ollama is not responding properly. Status: {health_resp.status_code}"
            except Exception as e:
                return f"Cannot reach Ollama server at {url}. Error: {str(e)}"
            # Generation request
            resp = await client.post(
                f"{url}/api/generate",
                json=data,
                headers={"Content-Type": "application/json"}
            )
            print(f"Ollama generate response status: {resp.status_code}")
            if resp.status_code == 200:
                result = resp.json()
                response_text = result.get("response", "")
                if response_text:
                    return response_text
                else:
                    return f"Ollama returned empty response. Full response: {result}"
            else:
                error_text = resp.text
                return f"Ollama API error (HTTP {resp.status_code}): {error_text}"
    except httpx.TimeoutException:
        return f"Timeout connecting to Ollama at {url}. The model might be loading or the server is slow."
    except httpx.ConnectError:
        return f"Connection failed to Ollama at {url}. Check if Ollama is running and accessible from the container."
    except Exception as e:
        return f"Unexpected error calling Ollama: {str(e)}"

def get_groq_headers():
    return {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

async def ask_llm_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY not configured. Please set the GROQ_API_KEY environment variable."
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = get_groq_headers()
    data = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    try:
        print(f"Calling Groq API with model: {GROQ_MODEL}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=data)
            print(f"Groq API response status: {resp.status_code}")
            
            if resp.status_code != 200:
                error_text = resp.text
                print(f"Groq API error response: {error_text}")
                return f"Groq API error (HTTP {resp.status_code}): {error_text}"
            
            result = resp.json()
            print(f"Groq API response: {result}")
            
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                print(f"Groq API content length: {len(content)}")
                return content
            else:
                print(f"Unexpected Groq API response format: {result}")
                return f"Unexpected Groq API response format: {result}"
                
    except httpx.TimeoutException:
        return "Error: Groq API request timed out after 60 seconds."
    except httpx.ConnectError:
        return "Error: Cannot connect to Groq API. Check your internet connection."
    except Exception as e:
        print(f"Groq API exception: {str(e)}")
        return f"Groq API error: {str(e)}"

# --- Focused log selection for root cause analysis ---
def select_focused_logs_for_anomaly(logs, anomaly_text=None, window=10, max_logs=20):
    # If anomaly_text is provided, try to find the log index with matching message
    if anomaly_text:
        for i, log in enumerate(reversed(logs)):
            if anomaly_text.lower() in json.dumps(log, default=str).lower():
                # Found anomaly log, select window around it
                start = max(0, len(logs) - i - window)
                end = min(len(logs), len(logs) - i + window)
                return logs[start:end]
    # If no anomaly or not found, fallback to last N error logs
    error_logs = [log for log in logs if log.get("level") == "ERROR" or "error" in log.get("message", "").lower()]
    if error_logs:
        return error_logs[-max_logs:]
    # Fallback: last N logs
    return logs[-max_logs:]

async def ai_incident_analysis(anomaly, logs, metrics, dependencies=None, cache_key=None):
    # --- Caching logic ---
    now = time.time()
    if cache_key and cache_key in root_cause_cache:
        cached = root_cause_cache[cache_key]
        if now - cached["timestamp"] < CACHE_TTL_SECONDS:
            return cached["result"]
    # --- Flexible log selection ---
    if anomaly and anomaly != "No anomalies detected, manual analysis":
        focused_logs = select_focused_logs_for_anomaly(logs, anomaly_text=anomaly)
        prompt_type = "incident"
    else:
        # No anomaly: use last N error logs, or last N logs if no errors
        error_logs = [log for log in logs if log.get("level") == "ERROR" or "error" in log.get("message", "").lower()]
        focused_logs = error_logs[-20:] if error_logs else logs[-20:]
        prompt_type = "general"
    recent_logs = focused_logs[-20:]
    if not recent_logs:
        recent_logs = [{"message": "No recent logs available."}]
    if not metrics:
        metrics = {"total": 0, "errors": 0, "performance_metrics": {"error_rate": 0}}
    # --- Updated prompt for strict JSON output ---
    if prompt_type == "incident":
        prompt = f"""You are an SRE analyzing a system incident. Please provide a concise analysis.

INCIDENT DETAILS:\nAnomaly: {anomaly}

RECENT LOGS (last {len(recent_logs)}):\n{chr(10).join([json.dumps(log, default=str)[:200] + '...' if len(json.dumps(log, default=str)) > 200 else json.dumps(log, default=str) for log in recent_logs])}

METRICS SUMMARY:\n- Total requests: {metrics.get('total', 0)}\n- Error count: {metrics.get('errors', 0)}\n- Error rate: {metrics.get('performance_metrics', {}).get('error_rate', 0):.2f}%

SERVICE DEPENDENCIES: {dependencies or 'N/A'}

Respond ONLY with valid JSON. Do NOT include any explanation, markdown, or comments. Your entire response must be a single valid JSON object, with no text before or after.
{{
  \"summary\": \"...\",
  \"root_cause\": \"...\",
  \"actions\": [\"...\", \"...\"],
  \"prevention\": [\"...\", \"...\"],
  \"confidence\": \"...\",
  \"evidence\": [\"...\", \"...\"]
}}
"""
    else:
        prompt = f"""You are an SRE reviewing system logs. No explicit anomaly was detected, but please review the following logs and metrics for any issues, unusual patterns, or potential risks.\n\nLOG SAMPLE (last {len(recent_logs)}):\n{chr(10).join([json.dumps(log, default=str)[:200] + '...' if len(json.dumps(log, default=str)) > 200 else json.dumps(log, default=str) for log in recent_logs])}\n\nMETRICS SUMMARY:\n- Total requests: {metrics.get('total', 0)}\n- Error count: {metrics.get('errors', 0)}\n- Error rate: {metrics.get('performance_metrics', {}).get('error_rate', 0):.2f}%\n\nSERVICE DEPENDENCIES: {dependencies or 'N/A'}\n\nRespond ONLY with valid JSON. Do NOT include any explanation, markdown, or comments. Your entire response must be a single valid JSON object, with no text before or after.\n{{\n  \"summary\": \"...\",\n  \"root_cause\": \"...\",\n  \"actions\": [\"...\", \"...\"],\n  \"prevention\": [\"...\", \"...\"],\n  \"confidence\": \"...\",\n  \"evidence\": [\"...\", \"...\"]\n}}\n"""
    ai_result = await ask_llm_groq(prompt)
    # --- Try to parse as JSON, removing comment lines ---
    parsed_result = None
    if isinstance(ai_result, str):
        try:
            # Extract JSON block
            start = ai_result.find('{')
            end = ai_result.rfind('}')
            if start != -1 and end != -1:
                json_str = ai_result[start:end+1]
                # Remove lines starting with // (comments)
                json_str = '\n'.join(line for line in json_str.splitlines() if not line.strip().startswith('//'))
                parsed_result = json.loads(json_str)
        except Exception as e:
            parsed_result = None
    # If parsing failed, fallback to string in a single field
    if not parsed_result:
        parsed_result = {
            "summary": None,
            "root_cause": ai_result if isinstance(ai_result, str) else str(ai_result),
            "actions": [],
            "prevention": [],
            "confidence": None,
            "evidence": []
        }
    result = {
        "anomalies": anomaly_cache,
        "root_cause": parsed_result
    }
    # Cache the result
    if cache_key:
        root_cause_cache[cache_key] = {"timestamp": now, "result": result}
    return result

async def ai_log_summary(logs, metrics, dependencies=None):
    # Limit to last 20 logs, and truncate each log string
    max_logs = 30
    recent_logs = logs[-max_logs:]
    if not recent_logs:
        recent_logs = [{"message": "No recent logs available."}]
    if not metrics:
        metrics = {"total": 0, "errors": 0, "performance_metrics": {"error_rate": 0}}
    prompt = f"""You are an SRE reviewing system logs. Please provide a concise summary of the last {len(recent_logs)} logs.

LOG SAMPLE (last {len(recent_logs)}):
{chr(10).join([json.dumps(log, default=str)[:200] + "..." if len(json.dumps(log, default=str)) > 200 else json.dumps(log, default=str) for log in recent_logs])}

METRICS SUMMARY:
- Total requests: {metrics.get('total', 0)}
- Error count: {metrics.get('errors', 0)}
- Error rate: {metrics.get('performance_metrics', {}).get('error_rate', 0):.2f}%

SERVICE DEPENDENCIES: {dependencies or 'N/A'}

Please provide:
1. OVERALL SUMMARY (2-3 sentences)
2. NOTABLE TRENDS OR PATTERNS (1-2 sentences)
3. ANY RECOMMENDATIONS (1-2 bullet points)

Keep response under 300 words.
"""
    ai_result = await ask_llm_groq(prompt)
    return {
        "summary": ai_result
    }

# --- Background Task ---
async def background_log_scanner():
    """Enhanced background log scanner with Prometheus integration"""
    global parsed_logs, metrics_summary, anomaly_cache, prometheus_metrics
    last_size = 0
    
    while True:
        try:
            # Load and parse logs
            logs = load_logs()
            if len(logs) != last_size:
                parsed_logs = logs
                metrics_summary = analyze_logs(logs)
                anomaly_cache = detect_anomalies(logs)
                last_size = len(logs)
            
            # Scrape Prometheus metrics
            prometheus_metrics = await scrape_prometheus()
            
        except Exception as e:
            print(f"Error in background scanner: {e}")
        
        await asyncio.sleep(30)  # Update every 30 seconds

# --- Authentication Endpoints ---
@app.post("/register")
async def register_user(data: RegisterModel):
    """Register a new user (persistent, MongoDB)"""
    existing = users_collection.find_one({"email": data.email})
    if existing:
        return {"status": "error", "msg": "Email already registered"}
    hashed_pw = bcrypt.hash(data.password)
    user_doc = {
        "email": data.email,
        "passwordHash": hashed_pw,
        "createdAt": datetime.utcnow(),
        "lastLoginAt": None,
        "sessionCount": 0
    }
    users_collection.insert_one(user_doc)
    return {"status": "success", "msg": "User registered successfully"}

@app.post("/login")
async def login_user(data: LoginModel):
    """Login a user (persistent, MongoDB)"""
    user = users_collection.find_one({"email": data.email})
    if not user or not bcrypt.verify(data.password, user["passwordHash"]):
        return {"status": "error", "msg": "Invalid credentials"}
    # Update user stats
    users_collection.update_one({"_id": user["_id"]}, {"$set": {"lastLoginAt": datetime.utcnow()}, "$inc": {"sessionCount": 1}})
    # Create JWT token
    token = create_access_token({"email": data.email})
    return {"status": "success", "access_token": token}

# --- API Endpoints ---
@app.get("/api/summary")
async def api_summary():
    return {"summary": metrics_summary, "anomalies": anomaly_cache}

@app.get("/api/metrics")
async def api_metrics():
    return {
        "log_metrics": metrics_summary, 
        "prometheus_metrics": prometheus_metrics
    }

@app.get("/api/ai_analysis")
async def api_ai_analysis(
    time_window_minutes: int = Query(15, ge=1, le=120),
    log_count: int = Query(None, ge=1, le=1000),
    anomaly: str = Query(None, description="Optional anomaly description"),
    mode: str = Query("root_cause", description="Analysis mode: 'root_cause' or 'summary'")
):
    now = datetime.now()
    window_start = now - timedelta(minutes=time_window_minutes)
    logs_window = [
        log for log in parsed_logs
        if "timestamp" in log and dateutil_parser.parse(log["timestamp"]).replace(tzinfo=None) >= window_start.replace(tzinfo=None)
    ]
    if log_count is not None:
        logs_window = parsed_logs[-log_count:]
    metrics_snapshot = metrics_summary.copy() if metrics_summary else {}
    dependencies = "auth_service -> order_service -> catalog_service (example)"
    if mode == "summary":
        ai_result = await ai_log_summary(logs_window, metrics_snapshot, dependencies)
        return {
            "mode": mode,
            "log_count": len(logs_window),
            "ai_summary": ai_result
        }
    else:
        # --- Use anomaly and time window as cache key ---
        cache_key = f"{anomaly or 'manual'}|{window_start.isoformat()}|{len(logs_window)}"
        ai_result = await ai_incident_analysis(anomaly or "Manual analysis requested", logs_window, metrics_snapshot, dependencies, cache_key=cache_key)
        return {
            "anomaly": anomaly or "Manual analysis requested",
            "time_window_minutes": time_window_minutes,
            "log_count": len(logs_window),
            "ai_analysis": ai_result
        }

@app.get("/api/root_cause")
async def api_root_cause():
    # Always run AI analysis, even if no anomalies detected
    now = datetime.now()
    window_start = now - timedelta(minutes=15)
    logs_window = [
        log for log in parsed_logs
        if "timestamp" in log and dateutil_parser.parse(log["timestamp"]).replace(tzinfo=None) >= window_start.replace(tzinfo=None)
    ]
    metrics_snapshot = metrics_summary.copy() if metrics_summary else {}
    dependencies = "auth_service -> order_service -> catalog_service (example)"
    anomaly_text = "; ".join(anomaly_cache) if anomaly_cache else "No anomalies detected, manual analysis"
    ai_result = await ai_incident_analysis(anomaly_text, logs_window, metrics_snapshot, dependencies)
    return {
        "anomalies": anomaly_cache,
        "root_cause": ai_result
    }

@app.get("/api/health")
async def api_health():
    """Comprehensive health check endpoint"""
    prometheus_healthy = "prometheus_error" not in prometheus_metrics
    logs_healthy = len(parsed_logs) > 0
    
    # Check if services are responding
    services_healthy = True
    if "targets" in prometheus_metrics:
        for target in prometheus_metrics["targets"]:
            if target.get("health") != "up":
                services_healthy = False
                break
    
    overall_health = prometheus_healthy and logs_healthy and services_healthy
    
    return {
        "status": "healthy" if overall_health else "unhealthy",
        "components": {
            "prometheus": "healthy" if prometheus_healthy else "unhealthy",
            "logs": "healthy" if logs_healthy else "unhealthy", 
            "services": "healthy" if services_healthy else "unhealthy"
        },
        "metrics": {
            "total_logs": len(parsed_logs),
            "total_errors": metrics_summary.get("errors", 0),
            "active_anomalies": len(anomaly_cache)
        }
    }

@app.get("/api/analytics")
async def api_analytics():
    """Detailed analytics endpoint"""
    return {
        "log_analytics": {
            "total_requests": metrics_summary.get("total", 0),
            "error_rate": f"{(metrics_summary.get('errors', 0) / max(metrics_summary.get('total', 1), 1)) * 100:.2f}%",
            "error_types": metrics_summary.get("error_types", {}),
            "response_codes": metrics_summary.get("response_codes", {}),
            "latency_stats": metrics_summary.get("performance_metrics", {}),
            "services": metrics_summary.get("services", {}),
            "time_series": metrics_summary.get("time_series", {})
        },
        "anomalies": anomaly_cache,
        "recent_errors": metrics_summary.get("last_10_errors", [])
    }

@app.get("/api/prometheus/status")
async def api_prometheus_status():
    """Detailed Prometheus status and metrics"""
    return {
        "status": "healthy" if "prometheus_error" not in prometheus_metrics else "unhealthy",
        "targets": prometheus_metrics.get("targets", []),
        "available_metrics": prometheus_metrics.get("available_metrics", []),
        "metrics_summary": {
            "http_requests": len(prometheus_metrics.get("http_requests_total", [])),
            "auth_attempts": len(prometheus_metrics.get("auth_attempts_total", [])),
            "jwt_tokens": len(prometheus_metrics.get("jwt_tokens_issued_total", [])),
            "db_operations": len(prometheus_metrics.get("db_operations_total", [])),
            "errors": len(prometheus_metrics.get("errors_total", []))
        }
    }

@app.get("/api/performance")
async def api_performance():
    """Performance-focused analytics"""
    perf_metrics = metrics_summary.get("performance_metrics", {})
    return {
        "latency_analysis": {
            "average_ms": perf_metrics.get("avg_latency_ms"),
            "p95_ms": perf_metrics.get("p95_latency_ms"),
            "p99_ms": perf_metrics.get("p99_latency_ms"),
            "min_ms": perf_metrics.get("min_latency_ms"),
            "max_ms": perf_metrics.get("max_latency_ms")
        },
        "throughput": {
            "total_requests": metrics_summary.get("total", 0),
            "success_rate": f"{perf_metrics.get('success_rate', 0):.2f}%",
            "error_rate": f"{perf_metrics.get('error_rate', 0):.2f}%"
        },
        "service_performance": metrics_summary.get("services", {}),
        "time_series": metrics_summary.get("time_series", {})
    }

@app.get("/api/errors/analysis")
async def api_errors_analysis():
    """Detailed error analysis"""
    return {
        "error_summary": {
            "total_errors": metrics_summary.get("errors", 0),
            "error_types": metrics_summary.get("error_types", {}),
            "error_rate": f"{metrics_summary.get('performance_metrics', {}).get('error_rate', 0):.2f}%"
        },
        "recent_errors": metrics_summary.get("last_10_errors", []),
        "service_errors": {
            service: data.get("errors", 0) 
            for service, data in metrics_summary.get("services", {}).items()
        },
        "response_code_errors": {
            code: count for code, count in metrics_summary.get("response_codes", {}).items()
            if code.startswith("4") or code.startswith("5")
        }
    }

@app.get("/api/ollama/test")
async def api_ollama_test():
    """Test Ollama connection and model availability with detailed diagnostics"""
    url = OLLAMA_URL.rstrip('/')
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test 1: Basic connectivity
            try:
                health_resp = await client.get(f"{url}/api/tags")
                if health_resp.status_code != 200:
                    return {
                        "status": "connection_failed",
                        "message": f"Ollama server responded with status {health_resp.status_code}",
                        "url": url,
                        "response": health_resp.text[:500]
                    }
                models = health_resp.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
            except Exception as e:
                return {
                    "status": "connection_error",
                    "message": f"Cannot connect to Ollama: {str(e)}",
                    "url": url
                }
            # Test 2: Check if our model is available
            if OLLAMA_MODEL not in model_names:
                return {
                    "status": "model_not_found",
                    "message": f"Model '{OLLAMA_MODEL}' not found in Ollama",
                    "available_models": model_names,
                    "url": url
                }
            # Test 3: Try a simple generation
            test_resp = await client.post(
                f"{url}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": "Hello, respond with 'working' if you can see this.",
                    "stream": False,
                    "options": {"max_tokens": 10}
                },
                timeout=30.0
            )
            if test_resp.status_code == 200:
                result = test_resp.json()
                response_text = result.get("response", "").strip()
                return {
                    "status": "working",
                    "message": "Ollama is working correctly",
                    "model": OLLAMA_MODEL,
                    "url": url,
                    "test_response": response_text,
                    "available_models": model_names
                }
            else:
                return {
                    "status": "generation_failed",
                    "message": f"Model generation failed with status {test_resp.status_code}",
                    "model": OLLAMA_MODEL,
                    "url": url,
                    "error": test_resp.text[:500]
                }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error testing Ollama: {str(e)}",
            "url": url,
            "model": OLLAMA_MODEL
        }

def tail_log_file(path: Path, n: int) -> list:
    """Efficiently read the last n lines from a file."""
    with path.open('rb') as f:
        f.seek(0, 2)
        filesize = f.tell()
        blocksize = 1024
        data = b''
        lines = []
        while len(lines) <= n and f.tell() > 0:
            seek_offset = min(f.tell(), blocksize)
            f.seek(-seek_offset, 1)
            data = f.read(seek_offset) + data
            f.seek(-seek_offset, 1)
            lines = data.split(b'\n')
        # Only keep the last n lines
        return [line.decode('utf-8', errors='replace') for line in lines[-n:] if line.strip()]

@app.get("/api/logs")
async def api_logs(
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),  # Reduced back to 1000 for faster loading
    level: str = Query(None),
    service: str = Query(None),
    time_start: str = Query(None),
    time_end: str = Query(None)
):
    """Efficiently stream and filter logs from disk with pagination and filtering."""
    # Read last (offset+limit) lines from the log file
    n = offset + limit
    lines = tail_log_file(LOG_PATH, n)
    logs = [parse_log_line(line) for line in lines]
    logs = logs[::-1]  # Newest first

    # Apply filters
    if level:
        logs = [log for log in logs if log.get("level", "").upper() == level.upper()]
    if service:
        logs = [log for log in logs if log.get("service", "").lower() == service.lower()]
    if time_start:
        try:
            start_dt = dateutil_parser.parse(time_start)
            logs = [log for log in logs if "timestamp" in log and dateutil_parser.parse(log["timestamp"]) >= start_dt]
        except Exception:
            pass
    if time_end:
        try:
            end_dt = dateutil_parser.parse(time_end)
            logs = [log for log in logs if "timestamp" in log and dateutil_parser.parse(log["timestamp"]) <= end_dt]
        except Exception:
            pass

    paginated_logs = logs[offset:offset+limit]
    return {
        "logs": paginated_logs,
        "total": len(logs),
        "offset": offset,
        "limit": limit,
        "last_updated": datetime.now().isoformat()
    }

@app.get("/api/services")
async def api_services():
    """Return per-service metrics: uptime, avg response time, latency, memory, cpu, error rate, status"""
    service_names = ["auth_service", "catalog_service", "order_service"]
    now = datetime.now()
    service_metrics = {}
    prom_metrics = prometheus_metrics
    def get_prom_value(metric_name, service_name):
        results = prom_metrics.get(metric_name, [])
        for entry in results:
            metric = entry.get('metric', {})
            if (
                metric.get('job') == service_name or
                metric.get('service') == service_name or
                service_name in metric.get('instance', '')
            ):
                try:
                    return float(entry.get('value', [None, 0])[1])
                except Exception:
                    continue
        return 0
    for name in service_names:
        logs = [log for log in parsed_logs if log.get("service") == name]
        errors = [log for log in logs if log.get("level") == "ERROR"]
        latencies = [
            (log.get("latency_ms") if log.get("latency_ms") is not None else log.get("duration_ms"))
            for log in logs
            if (log.get("latency_ms") is not None or log.get("duration_ms") is not None)
        ]
        latencies = [l for l in latencies if l is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else None
        # Uptime: use process_start_time_seconds from Prometheus
        process_start_time = get_prom_value("process_start_time_seconds", name)
        if process_start_time > 0:
            uptime = (time.time() - process_start_time) / 60  # in minutes
        else:
            uptime = None
        mem = get_prom_value("memory_used_mb", name)
        cpu = get_prom_value("cpu_percent", name)
        service_metrics[name] = {
            "name": name,
            "displayName": name.replace("_", " ").title(),
            "status": "healthy" if len(errors) == 0 else "warning",
            "uptime": round(uptime, 2) if uptime else None,  # in minutes
            "avg_latency": round(avg_latency, 2) if avg_latency else None,
            "memory_mb": round(mem, 2),
            "cpu_percent": round(cpu, 2),
            "error_rate": round((len(errors)/max(len(logs),1))*100, 2) if logs else 0,
            "total_requests": len(logs),
            "errors": len(errors),
        }
    return {"services": list(service_metrics.values())}

# MongoDB setup for per-user service registration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:secret@mongodb:27017")
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client[os.getenv("MONGO_DB", "appvital")]
services_collection = mongo_db["registered_services"]
logs_collection = mongo_db["logs"]  # <-- Add this line
users_collection = mongo_db["users"]  # <-- Add this line
metrics_history_collection = mongo_db["metrics_history"]  # <-- NEW: For historical metrics storage

# Create indexes for efficient querying
try:
    metrics_history_collection.create_index([
        ("service_name", pymongo.ASCENDING),
        ("timestamp", pymongo.DESCENDING)
    ])
    metrics_history_collection.create_index([
        ("service_name", pymongo.ASCENDING),
        ("metric_type", pymongo.ASCENDING),
        ("timestamp", pymongo.DESCENDING)
    ])
    print("Created indexes for metrics_history collection")
except Exception as e:
    print(f"Error creating indexes: {e}")

security = HTTPBearer()

def get_current_user_email(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        secret = os.getenv("JWT_SECRET", "mysecretkey")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload["email"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_registered_services_for_user(user_email: str):
    return list(services_collection.find({"owner": user_email}))

def mongo_to_dict(doc):
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

@app.get("/api/registered_services")
async def api_registered_services(user_email: str = Depends(get_current_user_email)):
    """Return registered services for the current user (MongoDB) with live metrics and status"""
    # Trigger metrics scraping for this user
    await scrape_metrics_for_user(user_email)
    
    services = get_registered_services_for_user(user_email)
    result = []
    for svc in services:
        svc_dict = mongo_to_dict(svc)
        name = svc_dict["name"]
        metrics_info = user_service_metrics.get(name, {})
        
        # Calculate uptime from Prometheus metrics
        uptime = None
        if metrics_info.get("metrics") and "process_start_time_seconds" in metrics_info["metrics"]:
            process_start_time = metrics_info["metrics"]["process_start_time_seconds"]
            if process_start_time > 0:
                uptime = (time.time() - process_start_time) / 60  # in minutes
        
        result.append({
            "name": svc_dict["name"],
            "url": svc_dict["url"],
            "createdAt": svc_dict.get("createdAt"),
            "owner": svc_dict["owner"],
            "_id": svc_dict["_id"],
            "status": metrics_info.get("status", "unknown"),
            "metrics": metrics_info.get("metrics", {}),
            "last_scraped": metrics_info.get("last_scraped"),
            "error": metrics_info.get("error"),
            "uptime": round(uptime, 2) if uptime else None
        })
    return {"registered_services": result}

@app.post("/api/registered_services")
async def register_service(data: dict, user_email: str = Depends(get_current_user_email)):
    """Register a new service for the current user (MongoDB)"""
    name = data.get('name')
    url = data.get('url')
    endpoints = data.get('endpoints', [])  # Accept endpoints if provided
    if not name or not url:
        return {"status": "error", "message": "Name and URL are required"}
    # Check if service already exists for this user
    existing = services_collection.find_one({"name": name, "owner": user_email})
    if existing:
        return {"status": "error", "message": f"Service '{name}' already exists"}
    doc = {
        "name": name,
        "url": url,
        "owner": user_email,
        "createdAt": datetime.utcnow(),
        "endpoints": endpoints  # Store endpoints if provided
    }
    services_collection.insert_one(doc)
    return {"status": "success", "message": f"Service '{name}' registered successfully"}

@app.post("/api/registered_services/{service_name}/endpoints")
async def add_or_update_service_endpoints(
    service_name: str,
    endpoints: list = Body(...),
    user_email: str = Depends(get_current_user_email)
):
    result = services_collection.update_one(
        {"name": service_name, "owner": user_email},
        {"$set": {"endpoints": endpoints}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"status": "success", "message": "Endpoints updated", "endpoints": endpoints}

@app.delete("/api/registered_services/{service_name}/endpoints")
async def delete_service_endpoint(
    service_name: str,
    path: str = Query(...),
    user_email: str = Depends(get_current_user_email)
):
    result = services_collection.update_one(
        {"name": service_name, "owner": user_email},
        {"$pull": {"endpoints": {"path": path}}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"status": "success", "message": f"Endpoint {path} removed"}

@app.post("/api/demo/register_services")
async def register_demo_services(data: dict):
    """Register demo services without authentication (only in demo mode)"""
    if os.getenv("DEMO_MODE") != "1":
        raise HTTPException(status_code=403, detail="Demo mode only")
    
    name = data.get('name')
    url = data.get('url')
    if not name or not url:
        return {"status": "error", "message": "Name and URL are required"}
    
    # Check if service already exists (demo services are global)
    existing = services_collection.find_one({"name": name})
    if existing:
        return {"status": "error", "message": f"Service '{name}' already exists"}
    
    doc = {
        "name": name,
        "url": url,
        "owner": "demo_user",  # Special owner for demo services
        "createdAt": datetime.utcnow(),
        "is_demo": True
    }
    services_collection.insert_one(doc)
    return {"status": "success", "message": f"Demo service '{name}' registered successfully"}

@app.delete("/api/registered_services")
async def delete_registered_service(name: str, user_email: str = Depends(get_current_user_email)):
    """Delete a registered service for the current user (MongoDB)"""
    result = services_collection.delete_one({"name": name, "owner": user_email})
    if result.deleted_count == 0:
        return {"status": "error", "message": f"Service '{name}' not found for user"}
    return {"status": "success", "message": f"Service '{name}' deleted successfully"}

@app.get("/api/test_metrics_endpoint")
async def test_metrics_endpoint(url: str):
    """Test if a metrics endpoint is accessible"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/metrics")
            if response.status_code == 200:
                return {"success": True, "message": "Metrics endpoint is accessible"}
            else:
                return {"success": False, "message": f"Metrics endpoint returned status {response.status_code}"}
    except Exception as e:
        return {"success": False, "message": f"Cannot connect to metrics endpoint: {str(e)}"}

@app.get("/api/system_overview")
async def api_system_overview(user_email: str = Depends(get_current_user_email)):
    # Trigger metrics scraping for this user
    await scrape_metrics_for_user(user_email)
    
    services_response = get_registered_services_for_user(user_email)
    services = []
    for svc in services_response:
        svc_dict = mongo_to_dict(svc)
        name = svc_dict["name"]
        metrics_info = user_service_metrics.get(name, {})
        services.append({
            "name": svc_dict["name"],
            "url": svc_dict["url"],
            "createdAt": svc_dict.get("createdAt"),
            "owner": svc_dict["owner"],
            "_id": svc_dict["_id"],
            "status": metrics_info.get("status", "unknown"),
            "metrics": metrics_info.get("metrics", {}),
            "last_scraped": metrics_info.get("last_scraped"),
            "error": metrics_info.get("error")
        })
    healthy_count = len([s for s in services if s.get("status") == "healthy"])
    unhealthy_count = len([s for s in services if s.get("status") != "healthy"])

    # --- NEW: Fetch all databases for this user ---
    dbs = list(db_mgmt_collection.find({"owner": user_email}))
    for db in dbs:
        db["_id"] = str(db["_id"])
    total = len(dbs)
    connected = len([db for db in dbs if db.get("status") == "connected"])
    disconnected = total - connected
    details = [
        {"name": db["name"], "status": db.get("status", "unknown")} for db in dbs
    ]
    return {
        "total_applications": len(services),
        "services": services,
        "databases": {
            "total": total,
            "connected": connected,
            "disconnected": disconnected,
            "details": details
        }
    }

@app.get("/api/databases")
async def api_databases(user_email: str = Depends(get_current_user_email)):
    """Return registered databases for the current user"""
    dbs = list(db_mgmt_collection.find({"owner": user_email}))
    for db in dbs:
        db["_id"] = str(db["_id"])
    return {"databases": dbs}


def check_postgres_health(uri):
    import time
    import re
    from urllib.parse import urlparse
    start = time.time()
    dsn = uri
    # If URI starts with postgresql://, parse and convert to DSN
    if uri.startswith("postgresql://"):
        parsed = urlparse(uri)
        user = parsed.username or ""
        password = parsed.password or ""
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        dbname = parsed.path.lstrip("/")
        dsn = f"host={host} port={port} dbname={dbname} user={user} password={password}"
    try:
        conn = psycopg2.connect(dsn, connect_timeout=3)
        cur = conn.cursor()
        cur.execute('SELECT 1;')
        cur.fetchone()
        response_time = int((time.time() - start) * 1000)
        host = conn.get_dsn_parameters().get('host', '-')
        port = conn.get_dsn_parameters().get('port', '-')
        cur.close()
        conn.close()
        return {
            "status": "connected",
            "response_time_ms": response_time,
            "host": host,
            "port": port,
            "error": None,
            "last_checked": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "disconnected",
            "response_time_ms": None,
            "host": "-",
            "port": "-",
            "error": str(e),
            "last_checked": datetime.utcnow().isoformat()
        }

def check_mysql_health(uri):
    import time
    try:
        import mysql.connector
    except ImportError:
        return {
            "status": "disconnected",
            "response_time_ms": None,
            "host": "-",
            "port": "-",
            "error": "mysql-connector-python not installed",
            "last_checked": datetime.utcnow().isoformat()
        }
    start = time.time()
    try:
        # Parse MySQL URI: mysql://user:pass@host:port/db
        from urllib.parse import urlparse
        parsed = urlparse(uri)
        conn = mysql.connector.connect(
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 3306,
            database=parsed.path.lstrip('/')
        )
        cur = conn.cursor()
        cur.execute('SELECT 1;')
        cur.fetchone()
        response_time = int((time.time() - start) * 1000)
        host = parsed.hostname or "-"
        port = parsed.port or 3306
        cur.close()
        conn.close()
        return {
            "status": "connected",
            "response_time_ms": response_time,
            "host": host,
            "port": port,
            "error": None,
            "last_checked": datetime.utcnow().isoformat()
        }
    except Exception as e:
        host = parsed.hostname if 'parsed' in locals() else "-"
        port = parsed.port if 'parsed' in locals() else "-"
        return {
            "status": "disconnected",
            "response_time_ms": None,
            "host": host,
            "port": port,
            "error": str(e),
            "last_checked": datetime.utcnow().isoformat()
        }

def check_database_health(db_type, uri):
    if db_type == "mongodb":
        return check_mongo_health(uri)
    elif db_type == "postgresql":
        return check_postgres_health(uri)
    elif db_type == "mysql":
        return check_mysql_health(uri)
    else:
        return {
            "status": "disconnected",
            "response_time_ms": None,
            "host": "-",
            "port": "-",
            "error": f"Unsupported database type: {db_type}",
            "last_checked": datetime.utcnow().isoformat()
        }

@app.post("/api/databases")
async def add_database(data: dict, user_email: str = Depends(get_current_user_email)):
    name = data.get("name")
    uri = data.get("uri")
    db_type = data.get("type", "mongodb")
    if not name or not uri or not db_type:
        return {"status": "error", "message": "Name, URI, and type are required"}
    existing = db_mgmt_collection.find_one({"name": name, "owner": user_email})
    if existing:
        return {"status": "error", "message": f"Database '{name}' already exists"}
    health = check_database_health(db_type, uri)
    db_doc = {
        "name": name,
        "uri": uri,
        "type": db_type,
        "owner": user_email,
        **health
    }
    result = db_mgmt_collection.insert_one(db_doc)
    db_doc["_id"] = str(result.inserted_id)
    return {"status": "success", "message": f"Database '{name}' added successfully", **db_doc}


@app.get("/api/databases")
async def api_databases():
    """Return all registered databases with their latest status."""
    dbs = list(db_mgmt_collection.find({}))
    for db in dbs:
        db["_id"] = str(db["_id"])
    return {"databases": dbs}

@app.delete("/api/databases")
async def remove_database(name: str, user_email: str = Depends(get_current_user_email)):
       result = db_mgmt_collection.delete_one({"name": name, "owner": user_email})
       if result.deleted_count == 0:
           return {"status": "error", "message": f"Database '{name}' not found for user"}
       return {"status": "success", "message": f"Database '{name}' removed successfully"}

# --- Periodic Health Check ---
async def background_db_health_checker():
    while True:
        dbs = list(db_mgmt_collection.find({}))
        for db in dbs:
            uri = db.get("uri")
            db_type = db.get("type", "mongodb")
            if not uri:
                continue
            health = check_database_health(db_type, uri)
            db_mgmt_collection.update_one({"_id": db["_id"]}, {"$set": health})
        await asyncio.sleep(60)  # Check every 60 seconds

@app.post("/api/ingest_log")
async def ingest_logs(data: dict):
    """Ingest logs from services"""
    try:
        logs = data.get("logs", [])
        if not logs:
            return {"status": "error", "message": "No logs provided"}
        # Insert logs into MongoDB
        if logs:
            logs_collection.insert_many(logs)
        # Add logs to the parsed_logs list for analysis (optional, keep for in-memory analytics)
        for log in logs:
            parsed_logs.append(log)
        return {"status": "success", "message": f"Successfully ingested {len(logs)} logs"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to ingest logs: {str(e)}"}

@app.post("/api/ingest_single_log")
async def ingest_single_log(log_entry: dict):
    """Ingest a single log entry"""
    try:
        logs_collection.insert_one(log_entry)
        parsed_logs.append(log_entry)
        return {"status": "success", "message": "Log ingested successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to ingest log: {str(e)}"}

@app.get("/api/debug/service-log-counts")
async def api_debug_service_log_counts():
    """Debug endpoint to check log counts per service"""
    service_counts = {}
    total_logs = len(parsed_logs)
    
    # Count logs by service
    for log in parsed_logs:
        service = log.get("service", "unknown")
        if service not in service_counts:
            service_counts[service] = {"total": 0, "errors": 0, "info": 0, "warning": 0}
        
        service_counts[service]["total"] += 1
        level = log.get("level", "").upper()
        if level == "ERROR":
            service_counts[service]["errors"] += 1
        elif level == "INFO":
            service_counts[service]["info"] += 1
        elif level == "WARNING":
            service_counts[service]["warning"] += 1
    
    # Get sample logs for each service
    sample_logs = {}
    for service in service_counts.keys():
        service_logs = [log for log in parsed_logs if log.get("service") == service]
        sample_logs[service] = service_logs[-5:] if service_logs else []  # Last 5 logs
    
    return {
        "total_logs": total_logs,
        "service_counts": service_counts,
        "sample_logs": sample_logs,
        "log_file_exists": LOG_PATH.exists(),
        "log_file_size": LOG_PATH.stat().st_size if LOG_PATH.exists() else 0,
        "last_updated": datetime.now().isoformat()
    }

@app.get("/api/debug/log-sample")
async def api_debug_log_sample():
    # Return the last 20 error logs with service and level fields
    error_logs = [log for log in parsed_logs if log.get("level") == "ERROR"]
    return {"error_logs": error_logs[-20:]}

@app.get("/api/debug/service-error-counts")
async def api_debug_service_error_counts():
    # Count ERROR logs per service
    error_counts = {}
    for log in parsed_logs:
        if log.get("level") == "ERROR":
            service = log.get("service", "unknown")
            error_counts[service] = error_counts.get(service, 0) + 1
    return {"service_error_counts": error_counts}

@app.get("/api/metrics/error_rate_timeseries")
async def error_rate_timeseries(
    window: str = Query("24h", description="Time window, e.g. 24h, 1h, 7d"),
    interval: str = Query("1h", description="Interval, e.g. 1h, 15m, 5m")
):
    """Return error rate over time as a list of time buckets."""
    # Parse window and interval
    now = datetime.utcnow()
    if window.endswith("h"):
        window_td = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        window_td = timedelta(days=int(window[:-1]))
    elif window.endswith("m"):
        window_td = timedelta(minutes=int(window[:-1]))
    else:
        window_td = timedelta(hours=24)
    if interval.endswith("h"):
        interval_td = timedelta(hours=int(interval[:-1]))
    elif interval.endswith("d"):
        interval_td = timedelta(days=int(interval[:-1]))
    elif interval.endswith("m"):
        interval_td = timedelta(minutes=int(interval[:-1]))
    else:
        interval_td = timedelta(hours=1)
    start_time = now - window_td
    # Prepare buckets
    buckets = defaultdict(lambda: {"total": 0, "errors": 0})
    logs = parsed_logs if parsed_logs else load_logs()
    interval_seconds = int(interval_td.total_seconds())
    for log in logs:
        ts = log.get("timestamp")
        if not ts:
            continue
        try:
            log_time = dateutil_parser.parse(ts).replace(tzinfo=None)
        except Exception:
            continue
        if log_time < start_time or log_time > now:
            continue
        # Robust bucket start calculation
        bucket_start_ts = int((log_time.timestamp() // interval_seconds) * interval_seconds)
        buckets[bucket_start_ts]["total"] += 1
        if log.get("level") == "ERROR" or ("error" in log.get("message", "").lower()):
            buckets[bucket_start_ts]["errors"] += 1
    # Format result
    result = []
    for bucket in sorted(buckets.keys()):
        total = buckets[bucket]["total"]
        errors = buckets[bucket]["errors"]
        error_rate = (errors / total * 100) if total > 0 else 0.0
        result.append({
            "time": bucket,
            "error_rate": round(error_rate, 2),
            "total": total,
            "errors": errors
        })
    return result

# --- Real Metrics Endpoints for Frontend Charts ---
@app.get("/api/metrics/http_requests_timeseries")
async def http_requests_timeseries(
    window: str = Query("24h"),
    interval: str = Query("1h")
):
    now = datetime.utcnow()
    # Parse window and interval
    if window.endswith("h"):
        window_td = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        window_td = timedelta(days=int(window[:-1]))
    elif window.endswith("m"):
        window_td = timedelta(minutes=int(window[:-1]))
    else:
        window_td = timedelta(hours=24)
    if interval.endswith("h"):
        interval_td = timedelta(hours=int(interval[:-1]))
    elif interval.endswith("d"):
        interval_td = timedelta(days=int(interval[:-1]))
    elif interval.endswith("m"):
        interval_td = timedelta(minutes=int(interval[:-1]))
    else:
        interval_td = timedelta(hours=1)
    start_time = now - window_td
    buckets = defaultdict(lambda: {"total": 0})
    logs = parsed_logs if parsed_logs else load_logs()
    interval_seconds = int(interval_td.total_seconds())
    for log in logs:
        ts = log.get("timestamp")
        if not ts:
            continue
        try:
            log_time = dateutil_parser.parse(ts).replace(tzinfo=None)
        except Exception:
            continue
        if log_time < start_time or log_time > now:
            continue
        bucket_start_ts = int((log_time.timestamp() // interval_seconds) * interval_seconds)
        buckets[bucket_start_ts]["total"] += 1
    result = []
    for bucket in sorted(buckets.keys()):
        result.append({
            "time": bucket,
            "total": buckets[bucket]["total"]
        })
    return result

@app.get("/api/metrics/response_time_timeseries")
async def response_time_timeseries(
    window: str = Query("24h"),
    interval: str = Query("1h")
):
    now = datetime.utcnow()
    if window.endswith("h"):
        window_td = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        window_td = timedelta(days=int(window[:-1]))
    elif window.endswith("m"):
        window_td = timedelta(minutes=int(window[:-1]))
    else:
        window_td = timedelta(hours=24)
    if interval.endswith("h"):
        interval_td = timedelta(hours=int(interval[:-1]))
    elif interval.endswith("d"):
        interval_td = timedelta(days=int(interval[:-1]))
    elif interval.endswith("m"):
        interval_td = timedelta(minutes=int(interval[:-1]))
    else:
        interval_td = timedelta(hours=1)
    start_time = now - window_td
    buckets = defaultdict(lambda: {"count": 0, "sum": 0.0})
    logs = parsed_logs if parsed_logs else load_logs()
    interval_seconds = int(interval_td.total_seconds())
    for log in logs:
        ts = log.get("timestamp")
        latency = log.get("latency_ms") or log.get("duration_ms")
        if not ts or latency is None:
            continue
        try:
            log_time = dateutil_parser.parse(ts).replace(tzinfo=None)
        except Exception:
            continue
        if log_time < start_time or log_time > now:
            continue
        bucket_start_ts = int((log_time.timestamp() // interval_seconds) * interval_seconds)
        buckets[bucket_start_ts]["count"] += 1
        buckets[bucket_start_ts]["sum"] += latency
    result = []
    for bucket in sorted(buckets.keys()):
        count = buckets[bucket]["count"]
        avg = buckets[bucket]["sum"] / count if count > 0 else 0
        result.append({
            "time": bucket,
            "avg_response_time_ms": round(avg, 2),
            "count": count
        })
    return result

@app.get("/api/metrics/cpu_usage_timeseries")
async def cpu_usage_timeseries(
    window: str = Query("24h"),
    interval: str = Query("1h")
):
    end = int(time.time())
    if window.endswith("h"):
        window_td = int(window[:-1]) * 3600
    elif window.endswith("d"):
        window_td = int(window[:-1]) * 86400
    elif window.endswith("m"):
        window_td = int(window[:-1]) * 60
    else:
        window_td = 24 * 3600
    start = end - window_td
    # Prometheus step in seconds
    if interval.endswith("h"):
        step = int(interval[:-1]) * 3600
    elif interval.endswith("d"):
        step = int(interval[:-1]) * 86400
    elif interval.endswith("m"):
        step = int(interval[:-1]) * 60
    else:
        step = 3600
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={
                "query": "avg(cpu_percent) by (service)",
                "start": start,
                "end": end,
                "step": step
            }
        )
        data = resp.json()
    # Aggregate by bucket
    buckets = {}
    for series in data.get("data", {}).get("result", []):
        service = series["metric"].get("service", "all")
        for v in series["values"]:
            ts, value = v
            bucket_ts = int((float(ts) // step) * step)
            key = (service, bucket_ts)
            if key not in buckets:
                buckets[key] = []
            buckets[key].append(float(value))
    result = []
    for (service, bucket_ts), values in buckets.items():
        avg_value = sum(values) / len(values)
        result.append({
            "time": datetime.utcfromtimestamp(bucket_ts).isoformat() + "Z",
            "service": service,
            "cpu_percent": avg_value
        })
    # Sort by time
    result.sort(key=lambda x: x["time"])
    return result

@app.get("/api/metrics/memory_usage_timeseries")
async def memory_usage_timeseries(
    window: str = Query("24h"),
    interval: str = Query("1h")
):
    end = int(time.time())
    if window.endswith("h"):
        window_td = int(window[:-1]) * 3600
    elif window.endswith("d"):
        window_td = int(window[:-1]) * 86400
    elif window.endswith("m"):
        window_td = int(window[:-1]) * 60
    else:
        window_td = 24 * 3600
    start = end - window_td
    if interval.endswith("h"):
        step = int(interval[:-1]) * 3600
    elif interval.endswith("d"):
        step = int(interval[:-1]) * 86400
    elif interval.endswith("m"):
        step = int(interval[:-1]) * 60
    else:
        step = 3600
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={
                "query": "avg(memory_used_mb) by (service)",
                "start": start,
                "end": end,
                "step": step
            }
        )
        data = resp.json()
    buckets = {}
    for series in data.get("data", {}).get("result", []):
        service = series["metric"].get("service", "all")
        for v in series["values"]:
            ts, value = v
            bucket_ts = int((float(ts) // step) * step)
            key = (service, bucket_ts)
            if key not in buckets:
                buckets[key] = []
            buckets[key].append(float(value))
    result = []
    for (service, bucket_ts), values in buckets.items():
        avg_value = sum(values) / len(values)
        result.append({
            "time": datetime.utcfromtimestamp(bucket_ts).isoformat() + "Z",
            "service": service,
            "memory_mb": avg_value
        })
    result.sort(key=lambda x: x["time"])
    return result

@app.get("/api/metrics/response_code_distribution")
async def response_code_distribution(
    window: str = Query("24h")
):
    now = datetime.utcnow()
    if window.endswith("h"):
        window_td = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        window_td = timedelta(days=int(window[:-1]))
    elif window.endswith("m"):
        window_td = timedelta(minutes=int(window[:-1]))
    else:
        window_td = timedelta(hours=24)
    start_time = now - window_td
    logs = parsed_logs if parsed_logs else load_logs()
    code_counts = {}
    for log in logs:
        ts = log.get("timestamp")
        code = str(log.get("status_code") or log.get("status"))
        if not ts or not code:
            continue
        try:
            log_time = dateutil_parser.parse(ts).replace(tzinfo=None)
        except Exception:
            continue
        if log_time < start_time or log_time > now:
            continue
        code_counts[code] = code_counts.get(code, 0) + 1
    return code_counts

# --- Expandable: Add more endpoints or analysis as needed --- 

@app.get("/api/all_registered_services")
async def api_all_registered_services():
    """Return ALL registered services from ALL users (for controller/demo purposes)"""
    try:
        # Get all registered services from all users
        all_services = list(services_collection.find({}))
        result = []
        for svc in all_services:
            svc_dict = mongo_to_dict(svc)
            name = svc_dict["name"]
            metrics_info = user_service_metrics.get(name, {})
            result.append({
                "name": svc_dict["name"],
                "url": svc_dict["url"],
                "createdAt": svc_dict.get("createdAt"),
                "owner": svc_dict["owner"],
                "_id": svc_dict["_id"],
                "status": metrics_info.get("status", "unknown"),
                "metrics": metrics_info.get("metrics", {}),
                "last_scraped": metrics_info.get("last_scraped"),
                "error": metrics_info.get("error")
            })
        return {"registered_services": result}
    except Exception as e:
        print(f"Error in api_all_registered_services: {e}")
        return {"registered_services": [], "error": str(e)}

@app.get("/api/test_endpoint")
async def test_endpoint():
    """Simple test endpoint to verify backend is working"""
    return {"message": "Backend is working", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/test_groq")
async def test_groq():
    """Test GROQ API connection and functionality"""
    try:
        if not GROQ_API_KEY:
            return {
                "status": "error",
                "message": "GROQ_API_KEY not configured",
                "groq_key_set": False
            }
        
        # Test with a simple prompt
        test_prompt = "Hello, please respond with 'GROQ API is working' if you can see this message."
        result = await ask_llm_groq(test_prompt)
        
        return {
            "status": "success" if "GROQ API is working" in result else "error",
            "message": result,
            "groq_key_set": True,
            "model": GROQ_MODEL
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Test failed: {str(e)}",
            "groq_key_set": bool(GROQ_API_KEY),
            "model": GROQ_MODEL
        }

@app.post("/api/reset_uptime/{service_name}")
async def reset_service_uptime(service_name: str, user_email: str = Depends(get_current_user_email)):
    """Reset uptime tracking for a specific service (for testing purposes)"""
    global service_uptime_tracker
    
    # Verify service ownership
    service_doc = services_collection.find_one({"name": service_name, "owner": user_email})
    if not service_doc:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    # Reset uptime tracking
    if service_name in service_uptime_tracker:
        del service_uptime_tracker[service_name]
        save_uptime_tracker()
        return {"status": "success", "message": f"Uptime tracking reset for {service_name}"}
    else:
        return {"status": "success", "message": f"No uptime tracking found for {service_name}"}

@app.get("/api/uptime_info/{service_name}")
async def get_uptime_info(service_name: str, user_email: str = Depends(get_current_user_email)):
    """Get uptime tracking information for a specific service"""
    global service_uptime_tracker
    
    # Verify service ownership
    service_doc = services_collection.find_one({"name": service_name, "owner": user_email})
    if not service_doc:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    # Get uptime info
    uptime_info = service_uptime_tracker.get(service_name, {})
    if uptime_info:
        current_time = time.time()
        uptime_minutes = (current_time - uptime_info["first_seen"]) / 60
        return {
            "service_name": service_name,
            "first_seen": datetime.fromtimestamp(uptime_info["first_seen"]).isoformat(),
            "last_healthy": datetime.fromtimestamp(uptime_info["last_healthy"]).isoformat(),
            "uptime_minutes": round(uptime_minutes, 2),
            "uptime_hours": round(uptime_minutes / 60, 2),
            "uptime_days": round(uptime_minutes / (60 * 24), 2)
        }
    else:
        return {
            "service_name": service_name,
            "message": "No uptime tracking data found"
        }

@app.get("/api/service_metrics/{service_name}")
async def api_service_metrics(
    service_name: str,
    window: str = Query("1h", description="Time window, e.g. 1h, 6h, 24h"),
    user_email: str = Depends(get_current_user_email)
):
    """Get detailed metrics for a specific service"""
    try:
        # Get the service from user_service_metrics
        service_data = user_service_metrics.get(service_name, {})
        
        if not service_data:
            raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
        
        # Get the service from database to verify ownership
        service_doc = services_collection.find_one({"name": service_name, "owner": user_email})
        if not service_doc:
            raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
        
        # Convert window to seconds for Prometheus queries
        window_seconds = {
            "1h": 3600,
            "6h": 21600,
            "24h": 86400
        }.get(window, 3600)
        
        # Get time series data from Prometheus
        metrics_data = {}
        
        # HTTP Requests Total
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query_range",
                    params={
                        "query": f'http_requests_total{{service="{service_name}"}}',
                        "start": time.time() - window_seconds,
                        "end": time.time(),
                        "step": "60"  # 1 minute intervals
                    },
                    timeout=10
                )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    metrics_data["http_requests_total"] = data["data"]["result"][0]["values"]
        except Exception as e:
            print(f"Error fetching http_requests_total: {e}")
        
        # Errors Total
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query_range",
                    params={
                        "query": f'errors_total{{service="{service_name}"}}',
                        "start": time.time() - window_seconds,
                        "end": time.time(),
                        "step": "60"
                    },
                    timeout=10
                )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    metrics_data["errors_total"] = data["data"]["result"][0]["values"]
        except Exception as e:
            print(f"Error fetching errors_total: {e}")
        
        # CPU Usage
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query_range",
                    params={
                        "query": f'cpu_percent{{service="{service_name}"}}',
                        "start": time.time() - window_seconds,
                        "end": time.time(),
                        "step": "60"
                    },
                    timeout=10
                )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    metrics_data["cpu_percent"] = data["data"]["result"][0]["values"]
        except Exception as e:
            print(f"Error fetching cpu_percent: {e}")
        
        # Memory Usage
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query_range",
                    params={
                        "query": f'memory_used_mb{{service="{service_name}"}}',
                        "start": time.time() - window_seconds,
                        "end": time.time(),
                        "step": "60"
                    },
                    timeout=10
                )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    metrics_data["memory_used_mb"] = data["data"]["result"][0]["values"]
        except Exception as e:
            print(f"Error fetching memory_used_mb: {e}")
        
        # Total Response Time (average)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query_range",
                    params={
                        "query": f'rate(total_response_ms_sum{{service="{service_name}"}}[{window}]) / rate(total_response_ms_count{{service="{service_name}"}}[{window}]) * 1000',
                        "start": time.time() - window_seconds,
                        "end": time.time(),
                        "step": "60"
                    },
                    timeout=10
                )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    metrics_data["total_response_ms"] = data["data"]["result"][0]["values"]
        except Exception as e:
            print(f"Error fetching total_response_ms: {e}")
        
        # Convert Prometheus format to frontend format
        formatted_metrics = {}
        for metric_name, values in metrics_data.items():
            formatted_metrics[metric_name] = [
                {"timestamp": float(timestamp), "value": float(value)}
                for timestamp, value in values
            ]
        
        return {
            "service_name": service_name,
            "window": window,
            "metrics": formatted_metrics,
            "current_status": service_data.get("status", "unknown"),
            "last_scraped": service_data.get("last_scraped"),
            "current_metrics": service_data.get("metrics", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in service_metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/test_endpoint")
async def test_endpoint():
    """Simple test endpoint to verify backend is working"""
    return {"message": "Backend is working", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/service_metrics/{service_name}/summary")
async def api_service_metrics_summary(service_name: str):
    """Return service-specific metrics summary from logs for the Metrics tab."""
    # Filter logs for this service
    logs = [log for log in parsed_logs if log.get("service") == service_name]
    total_requests = len(logs)
    errors = [log for log in logs if log.get("level") == "ERROR" or "error" in log.get("message", "").lower()]
    error_count = len(errors)
    latencies = [
        (log.get("latency_ms") if log.get("latency_ms") is not None else log.get("duration_ms"))
        for log in logs
        if (log.get("latency_ms") is not None or log.get("duration_ms") is not None)
    ]
    latencies = [l for l in latencies if l is not None]
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0.0
    # Status: healthy if no errors in last 10 logs, else warning/down
    recent_logs = logs[-10:]
    recent_errors = [log for log in recent_logs if log.get("level") == "ERROR" or "error" in log.get("message", "").lower()]
    status = "healthy" if not recent_errors else ("warning" if error_count < total_requests else "down")
    return {
        "service": service_name,
        "total_requests": total_requests,
        "errors": error_count,
        "avg_latency_ms": round(avg_latency, 2) if avg_latency is not None else None,
        "error_rate": round(error_rate, 2),
        "status": status
    }

@app.get("/api/service_metrics/{service_name}/requests_timeseries")
async def service_requests_timeseries(
    service_name: str,
    window: str = Query("6h"),
    interval: str = Query("5m")
):
    now = datetime.utcnow()
    # Parse window and interval
    if window.endswith("h"):
        window_td = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        window_td = timedelta(days=int(window[:-1]))
    elif window.endswith("m"):
        window_td = timedelta(minutes=int(window[:-1]))
    else:
        window_td = timedelta(hours=6)
    if interval.endswith("h"):
        interval_td = timedelta(hours=int(interval[:-1]))
    elif interval.endswith("d"):
        interval_td = timedelta(days=int(interval[:-1]))
    elif interval.endswith("m"):
        interval_td = timedelta(minutes=int(interval[:-1]))
    else:
        interval_td = timedelta(minutes=5)
    start_time = now - window_td
    interval_seconds = int(interval_td.total_seconds())
    # Filter logs for this service
    logs = [log for log in parsed_logs if log.get("service") == service_name]
    # Bucket by interval
    buckets = defaultdict(lambda: {"total": 0})
    for log in logs:
        ts = log.get("timestamp")
        if not ts:
            continue
        try:
            log_time = dateutil_parser.parse(ts).replace(tzinfo=None)
        except Exception:
            continue
        if log_time < start_time or log_time > now:
            continue
        bucket_start_ts = int((log_time.timestamp() // interval_seconds) * interval_seconds)
        buckets[bucket_start_ts]["total"] += 1
    result = []
    for bucket in sorted(buckets.keys()):
        result.append({
            "time": bucket,
            "total": buckets[bucket]["total"]
        })
    return result

@app.get("/api/service_metrics/{service_name}/response_time_timeseries")
async def service_response_time_timeseries(
    service_name: str,
    window: str = Query("6h"),
    interval: str = Query("5m")
):
    now = datetime.utcnow()
    if window.endswith("h"):
        window_td = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        window_td = timedelta(days=int(window[:-1]))
    elif window.endswith("m"):
        window_td = timedelta(minutes=int(window[:-1]))
    else:
        window_td = timedelta(hours=6)
    if interval.endswith("h"):
        interval_td = timedelta(hours=int(interval[:-1]))
    elif interval.endswith("d"):
        interval_td = timedelta(days=int(interval[:-1]))
    elif interval.endswith("m"):
        interval_td = timedelta(minutes=int(interval[:-1]))
    else:
        interval_td = timedelta(minutes=5)
    start_time = now - window_td
    interval_seconds = int(interval_td.total_seconds())
    # Filter logs for this service
    logs = [log for log in parsed_logs if log.get("service") == service_name]
    # Bucket by interval
    buckets = defaultdict(lambda: {"count": 0, "sum": 0.0})
    for log in logs:
        ts = log.get("timestamp")
        latency = log.get("latency_ms") or log.get("duration_ms")
        if not ts or latency is None:
            continue
        try:
            log_time = dateutil_parser.parse(ts).replace(tzinfo=None)
        except Exception:
            continue
        if log_time < start_time or log_time > now:
            continue
        bucket_start_ts = int((log_time.timestamp() // interval_seconds) * interval_seconds)
        buckets[bucket_start_ts]["count"] += 1
        buckets[bucket_start_ts]["sum"] += latency
    result = []
    for bucket in sorted(buckets.keys()):
        count = buckets[bucket]["count"]
        avg = buckets[bucket]["sum"] / count if count > 0 else 0
        result.append({
            "time": bucket,
            "avg_response_time_ms": round(avg, 2),
            "count": count
        })
    return result

@app.get("/api/service_metrics/{service_name}/errors_timeseries")
async def service_errors_timeseries(
    service_name: str,
    window: str = Query("6h"),
    interval: str = Query("5m")
):
    now = datetime.utcnow()
    # Parse window and interval
    if window.endswith("h"):
        window_td = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        window_td = timedelta(days=int(window[:-1]))
    elif window.endswith("m"):
        window_td = timedelta(minutes=int(window[:-1]))
    else:
        window_td = timedelta(hours=6)
    if interval.endswith("h"):
        interval_td = timedelta(hours=int(interval[:-1]))
    elif interval.endswith("d"):
        interval_td = timedelta(days=int(interval[:-1]))
    elif interval.endswith("m"):
        interval_td = timedelta(minutes=int(interval[:-1]))
    else:
        interval_td = timedelta(minutes=5)
    start_time = now - window_td
    interval_seconds = int(interval_td.total_seconds())
    # Filter logs for this service
    logs = [log for log in parsed_logs if log.get("service") == service_name]
    # Bucket by interval
    buckets = defaultdict(lambda: {"errors": 0})
    for log in logs:
        ts = log.get("timestamp")
        if not ts:
            continue
        try:
            log_time = dateutil_parser.parse(ts).replace(tzinfo=None)
        except Exception:
            continue
        if log_time < start_time or log_time > now:
            continue
        if log.get("level") == "ERROR" or "error" in log.get("message", "").lower():
            bucket_start_ts = int((log_time.timestamp() // interval_seconds) * interval_seconds)
            buckets[bucket_start_ts]["errors"] += 1
    result = []
    for bucket in sorted(buckets.keys()):
        result.append({
            "time": bucket,
            "errors": buckets[bucket]["errors"]
        })
    return result

def save_metrics_history(service_name: str, metrics: dict, timestamp: float):
    """Store all metrics in a single document per timestamp, with rounded values and IST time, and in a specific field order."""
    try:
        # Convert timestamp to IST
        utc_dt = datetime.fromtimestamp(timestamp)
        ist = pytz.timezone('Asia/Kolkata')
        ist_dt = utc_dt.astimezone(ist)
        ist_str = ist_dt.strftime("%Y-%m-%d %H:%M:%S")

        doc = OrderedDict()
        doc["timestamp"] = ist_str
        doc["service"] = service_name
        # Add metrics in the required order
        if 'errors_total' in metrics:
            doc["errors_total"] = float(metrics['errors_total'])
        if 'cpu_percent' in metrics:
            doc["cpu_percent"] = round(metrics['cpu_percent'], 2)
        if 'memory_used_mb' in metrics:
            doc["memory_used_mb"] = round(metrics['memory_used_mb'], 2)
        if 'http_requests_total' in metrics:
            doc["http_requests_total"] = float(metrics['http_requests_total'])

        metrics_history_collection.insert_one(doc)
    except Exception as e:
        print(f"Error saving metrics history for {service_name}: {e}")

def cleanup_old_metrics_history(days_to_keep: int = 30):
    """Clean up old metrics data to prevent database bloat"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        result = metrics_history_collection.delete_many({
            "timestamp": {"$lt": cutoff_date}
        })
        if result.deleted_count > 0:
            print(f"Cleaned up {result.deleted_count} old metrics records")
    except Exception as e:
        print(f"Error cleaning up old metrics: {e}")

@app.get("/api/service_metrics/{service_name}/cpu_history")
async def service_cpu_history(
    service_name: str,
    window: str = Query("24h", description="Time window, e.g. 1h, 6h, 24h, 7d")
):
    now = datetime.utcnow()
    if window.endswith("h"):
        window_td = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        window_td = timedelta(days=int(window[:-1]))
    elif window.endswith("m"):
        window_td = timedelta(minutes=int(window[:-1]))
    else:
        window_td = timedelta(hours=24)
    start_time = now - window_td
    # Query by service and timestamp (new format)
    cursor = metrics_history_collection.find({
        "service": service_name,
        "timestamp": {"$gte": start_time.strftime("%Y-%m-%d %H:%M:%S")}
    }).sort("timestamp", 1)
    data = [
        {"time": doc["timestamp"], "cpu_percent": doc.get("cpu_percent")}
        for doc in cursor if "cpu_percent" in doc
    ]
    return {
        "service_name": service_name,
        "window": window,
        "data": data,
        "count": len(data)
    }

@app.get("/api/service_metrics/{service_name}/memory_history")
async def service_memory_history(
    service_name: str,
    window: str = Query("24h", description="Time window, e.g. 1h, 6h, 24h, 7d")
):
    now = datetime.utcnow()
    if window.endswith("h"):
        window_td = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        window_td = timedelta(days=int(window[:-1]))
    elif window.endswith("m"):
        window_td = timedelta(minutes=int(window[:-1]))
    else:
        window_td = timedelta(hours=24)
    start_time = now - window_td
    # Query by service and timestamp (new format)
    cursor = metrics_history_collection.find({
        "service": service_name,
        "timestamp": {"$gte": start_time.strftime("%Y-%m-%d %H:%M:%S")}
    }).sort("timestamp", 1)
    data = [
        {"time": doc["timestamp"], "memory_mb": doc.get("memory_used_mb")}
        for doc in cursor if "memory_used_mb" in doc
    ]
    return {
        "service_name": service_name,
        "window": window,
        "data": data,
        "count": len(data)
    }

@app.get("/api/service_metrics/{service_name}/load_forecast")
async def service_load_forecast(
    service_name: str,
    forecast_hours: int = Query(24, description="Hours to forecast", ge=1, le=168),
    user_email: str = Depends(get_current_user_email)
):
    """Get load forecasting data for a specific service based on historical patterns"""
    try:
        # Verify service ownership
        service_doc = services_collection.find_one({"name": service_name, "owner": user_email})
        if not service_doc:
            raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
        
        # Get historical data for the last 7 days to establish patterns
        now = datetime.utcnow()
        start_time = now - timedelta(days=7)
        
        # Get CPU and memory data
        cpu_cursor = metrics_history_collection.find({
            "service_name": service_name,
            "metric_type": "cpu_percent",
            "timestamp": {"$gte": start_time, "$lte": now}
        }).sort("timestamp", 1)
        
        memory_cursor = metrics_history_collection.find({
            "service_name": service_name,
            "metric_type": "memory_used_mb",
            "timestamp": {"$gte": start_time, "$lte": now}
        }).sort("timestamp", 1)
        
        # Process historical data for pattern analysis
        cpu_data = [doc["value"] for doc in cpu_cursor]
        memory_data = [doc["value"] for doc in memory_cursor]
        
        # Simple forecasting based on historical averages and trends
        # In a production system, you'd use more sophisticated ML models
        forecast_data = []
        
        if cpu_data and memory_data:
            # Calculate baseline averages
            avg_cpu = sum(cpu_data) / len(cpu_data)
            avg_memory = sum(memory_data) / len(memory_data)
            
            # Simple trend calculation (linear regression approximation)
            if len(cpu_data) > 1:
                cpu_trend = (cpu_data[-1] - cpu_data[0]) / len(cpu_data)
                memory_trend = (memory_data[-1] - memory_data[0]) / len(memory_data)
            else:
                cpu_trend = 0
                memory_trend = 0
            
            # Generate forecast points
            for hour in range(1, forecast_hours + 1):
                forecast_time = now + timedelta(hours=hour)
                forecast_cpu = max(0, min(100, avg_cpu + (cpu_trend * hour)))
                forecast_memory = max(0, avg_memory + (memory_trend * hour))
                
                forecast_data.append({
                    "time": forecast_time.isoformat() + "Z",
                    "cpu_percent": round(forecast_cpu, 2),
                    "memory_mb": round(forecast_memory, 2),
                    "confidence": "medium"  # Placeholder for ML confidence scores
                })
        
        return {
            "service_name": service_name,
            "forecast_hours": forecast_hours,
            "historical_data_points": len(cpu_data),
            "forecast": forecast_data,
            "baseline": {
                "avg_cpu_percent": round(sum(cpu_data) / len(cpu_data), 2) if cpu_data else 0,
                "avg_memory_mb": round(sum(memory_data) / len(memory_data), 2) if memory_data else 0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in service_load_forecast: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/service_metrics/{service_name}/errors_timeseries")
async def service_errors_timeseries(
    service_name: str,
    window: str = Query("6h"),
    interval: str = Query("5m")
):
    now = datetime.utcnow()
    # Parse window and interval
    if window.endswith("h"):
        window_td = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        window_td = timedelta(days=int(window[:-1]))
    elif window.endswith("m"):
        window_td = timedelta(minutes=int(window[:-1]))
    else:
        window_td = timedelta(hours=6)
    if interval.endswith("h"):
        interval_td = timedelta(hours=int(interval[:-1]))
    elif interval.endswith("d"):
        interval_td = timedelta(days=int(interval[:-1]))
    elif interval.endswith("m"):
        interval_td = timedelta(minutes=int(interval[:-1]))
    else:
        interval_td = timedelta(minutes=5)
    start_time = now - window_td
    interval_seconds = int(interval_td.total_seconds())
    # Filter logs for this service
    logs = [log for log in parsed_logs if log.get("service") == service_name]
    # Bucket by interval
    buckets = defaultdict(lambda: {"errors": 0})
    for log in logs:
        ts = log.get("timestamp")
        if not ts:
            continue
        try:
            log_time = dateutil_parser.parse(ts).replace(tzinfo=None)
        except Exception:
            continue
        if log_time < start_time or log_time > now:
            continue
        if log.get("level") == "ERROR" or "error" in log.get("message", "").lower():
            bucket_start_ts = int((log_time.timestamp() // interval_seconds) * interval_seconds)
            buckets[bucket_start_ts]["errors"] += 1
    result = []
    for bucket in sorted(buckets.keys()):
        result.append({
            "time": bucket,
            "errors": buckets[bucket]["errors"]
        })
    return result

def parse_mongo_uri(uri):
    try:
        parsed = urlparse(uri)
        host = parsed.hostname or "-"
        port = parsed.port or 27017
        return host, port
    except Exception:
        return "-", "-"

def check_mongo_health(uri):
    import time
    from pymongo import MongoClient as PyMongoClient
    start = time.time()
    try:
        client = PyMongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command('ping')
        response_time = int((time.time() - start) * 1000)
        host, port = parse_mongo_uri(uri)
        client.close()
        return {
            "status": "connected",
            "response_time_ms": response_time,
            "host": host,
            "port": port,
            "error": None,
            "last_checked": datetime.utcnow().isoformat()
        }
    except Exception as e:
        host, port = parse_mongo_uri(uri)
        return {
            "status": "disconnected",
            "response_time_ms": None,
            "host": host,
            "port": port,
            "error": str(e),
            "last_checked": datetime.utcnow().isoformat()
        }

# --- Registered Databases Collection ---
db_mgmt_collection = mongo_db["registered_databases"]

@app.post("/api/databases/test_connection")
async def test_database_connection(data: dict):
    db_type = data.get("type", "mongodb")
    uri = data.get("uri")
    if not uri or not db_type:
        return {"success": False, "message": "Type and URI are required"}
    health = check_database_health(db_type, uri)
    if health["status"] == "connected":
        return {"success": True, "message": f"Successfully connected to {db_type} database.", **health}
    else:
        return {"success": False, "message": health.get("error", "Connection failed"), **health}

