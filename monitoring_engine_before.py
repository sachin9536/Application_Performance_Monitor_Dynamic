
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse
import httpx
import time
import re
import os
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
import psutil
from dateutil import parser as dateutil_parser
from collections import defaultdict

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

LOG_PATH = Path("/app/logs/metrics.log")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(background_log_scanner())
    yield
    task.cancel()

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
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = get_groq_headers()
    data = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=data)
            resp.raise_for_status()
            result = resp.json()
            return result["choices"][0]["message"]["content"]
    except Exception as e:
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
    if prompt_type == "incident":
        prompt = f"""You are an SRE analyzing a system incident. Please provide a concise analysis.\n\nINCIDENT DETAILS:\nAnomaly: {anomaly}\n\nRECENT LOGS (last {len(recent_logs)}):\n{chr(10).join([json.dumps(log, default=str)[:200] + '...' if len(json.dumps(log, default=str)) > 200 else json.dumps(log, default=str) for log in recent_logs])}\n\nMETRICS SUMMARY:\n- Total requests: {metrics.get('total', 0)}\n- Error count: {metrics.get('errors', 0)}\n- Error rate: {metrics.get('performance_metrics', {}).get('error_rate', 0):.2f}%\n\nSERVICE DEPENDENCIES: {dependencies or 'N/A'}\n\nPlease provide:\n1. INCIDENT SUMMARY (2-3 sentences)\n2. LIKELY ROOT CAUSE (1-2 sentences)\n3. IMMEDIATE ACTIONS (2-3 bullet points)\n4. PREVENTION (1-2 recommendations)\n\nKeep response under 300 words.\n"""
    else:
        prompt = f"""You are an SRE reviewing system logs. No explicit anomaly was detected, but please review the following logs and metrics for any issues, unusual patterns, or potential risks.\n\nLOG SAMPLE (last {len(recent_logs)}):\n{chr(10).join([json.dumps(log, default=str)[:200] + '...' if len(json.dumps(log, default=str)) > 200 else json.dumps(log, default=str) for log in recent_logs])}\n\nMETRICS SUMMARY:\n- Total requests: {metrics.get('total', 0)}\n- Error count: {metrics.get('errors', 0)}\n- Error rate: {metrics.get('performance_metrics', {}).get('error_rate', 0):.2f}%\n\nSERVICE DEPENDENCIES: {dependencies or 'N/A'}\n\nPlease provide:\n1. OVERALL HEALTH SUMMARY (2-3 sentences)\n2. ANY ISSUES, RISKS, OR UNUSUAL PATTERNS (bullet points)\n3. RECOMMENDATIONS (1-2 bullet points)\n\nKeep response under 300 words.\n"""
    ai_result = await ask_llm_groq(prompt)
    result = {
        "anomalies": anomaly_cache,
        "root_cause": ai_result
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
    limit: int = Query(1000, ge=1, le=10000),
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
        latencies = [log.get("latency_ms") if log.get("latency_ms") is not None else log.get("duration_ms") for log in logs if log.get("latency_ms") is not None or log.get("duration_ms") is not None]
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
        bucket_key = datetime.utcfromtimestamp(bucket_start_ts).strftime("%Y-%m-%dT%H:%M:00Z")
        buckets[bucket_key]["total"] += 1
        if log.get("level") == "ERROR" or ("error" in log.get("message", "").lower()):
            buckets[bucket_key]["errors"] += 1
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
        bucket_key = datetime.utcfromtimestamp(bucket_start_ts).strftime("%Y-%m-%dT%H:%M:00Z")
        buckets[bucket_key]["total"] += 1
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
        bucket_key = datetime.utcfromtimestamp(bucket_start_ts).strftime("%Y-%m-%dT%H:%M:00Z")
        buckets[bucket_key]["count"] += 1
        buckets[bucket_key]["sum"] += latency
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
        code = str(log.get("status_code"))
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
