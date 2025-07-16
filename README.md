# 🏥 Health Monitoring System for Microservices

A comprehensive, enterprise-grade health monitoring system for microservices architecture built with FastAPI, MongoDB, Docker, and Prometheus. Features AI-powered root cause analysis using Ollama LLaMA 3 and a modern frontend dashboard.

---

## 🚀 Features

- **Microservices:** Auth, Order, Catalog (FastAPI, MongoDB, Prometheus metrics)
- **Prometheus Monitoring:** System, business, and HTTP metrics for all services
- **AI Root Cause Analysis:** Ollama LLaMA 3 integration for incident analysis
- **Structured Logging:** JSON logs, real-time log analysis, anomaly detection
- **Comprehensive Dashboard:** Real-time health, metrics, analytics, logs, and AI insights
- **Docker Compose Orchestration:** Easy local development and deployment

---

## 🏗️ Architecture

```
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Auth Service  │   │ Order Service │   │ Catalog Svc   │
│ 8001/8002     │   │ 8003/8004     │   │ 8005/8006     │
└──────┬────────┘   └──────┬────────┘   └──────┬────────┘
       │                   │                   │
       └─────────────┬─────┴─────┬─────────────┘
                     │           │
             ┌───────▼───────────▼───────┐
             │      MongoDB (27017)      │
             └─────────────┬─────────────┘
                           │
                  ┌────────▼────────┐
                  │  Prometheus     │
                  │   (9090)        │
                  └────────┬────────┘
                           │
         ┌─────────────────▼─────────────────┐
         │ Monitoring Engine (8000)          │
         │ Controller (traffic gen)          │
         │ Frontend Dashboard (React)        │
         └───────────────────────────────────┘
```

---

## 📦 Services Overview

### Auth Service

- User registration & sign-in (JWT)
- MongoDB for user storage
- Prometheus metrics: auth attempts, JWTs, DB ops, system
- `/register`, `/signin`, `/ping`, `/health`, `/metrics`

### Order Service

- Place and view orders (JWT required)
- MongoDB for orders
- Prometheus metrics: order ops, DB ops, system
- `/api/v1/order`, `/api/v1/orders`, `/ping`, `/health`, `/metrics`

### Catalog Service

- Product catalog CRUD (JWT required)
- MongoDB for products
- Prometheus metrics: product ops, stock updates, DB ops, system
- `/api/v1/add_product`, `/api/v1/update_stock`, `/api/v1/product`, `/api/v1/all_products`, `/ping`, `/health`, `/metrics`

### Monitoring Engine

- Aggregates logs, metrics, and Prometheus data
- AI-powered root cause analysis via Ollama
- Endpoints: `/api/health`, `/api/summary`, `/api/metrics`, `/api/performance`, `/api/analytics`, `/api/root_cause`, `/api/errors/analysis`, `/api/logs`, `/api/services`, `/api/ollama/test`

### Controller

- Generates synthetic traffic and error scenarios for testing

### Frontend Dashboard

- React app for real-time monitoring, analytics, logs, and AI insights
- Auto-refresh, manual refresh, color-coded status, error toasts

---

## 📊 Metrics Collected

- **HTTP Metrics:** `http_requests_total`, `http_request_duration_seconds`, `response_time_ms`
- **Business Metrics:** `auth_attempts_total`, `order_operations_total`, `product_operations_total`, `stock_updates_total`
- **Database Metrics:** `db_operations_total`, `db_operation_duration_seconds`
- **System Metrics:** `cpu_percent`, `memory_used_mb`, `process_start_time_seconds`
- **Error Metrics:** `errors_total`, `error_types`, `order_404`, `http_500`, `auth_failures`
- **JWT Metrics:** `jwt_tokens_issued_total`, `jwt_token_validations_total`

---

## 🛠️ Setup & Usage

### Prerequisites

- Docker & Docker Compose
- Python 3.8+
- Ollama (for AI analysis, optional)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd health-monitoring-auth_service_dev
   ```
2. **Start all services**
   ```bash
   docker-compose up --build
   ```
3. **Access the system:**

   - **Frontend Dashboard:** http://localhost:8000
   - **Prometheus:** http://localhost:9090
   - **Mongo Express:** http://localhost:8081
   - **Auth Service:** http://localhost:8001
   - **Order Service:** http://localhost:8003
   - **Catalog Service:** http://localhost:8005

4. **Seed the catalog (optional):**

   ```bash
   python seed_catalog.py
   ```

5. **Test endpoints:**
   - Register/sign in, get a JWT, and use it for order/catalog APIs.
   - Use `/api/root_cause` for AI analysis.

---

## 🧑‍💻 API Endpoints

### Monitoring Engine

- `GET /api/health` — System health
- `GET /api/summary` — Metrics summary
- `GET /api/metrics` — Detailed metrics
- `GET /api/performance` — Performance analytics
- `GET /api/analytics` — Analytics
- `GET /api/root_cause` — AI root cause analysis
- `GET /api/errors/analysis` — Error analysis
- `GET /api/logs` — Logs
- `GET /api/services` — Per-service metrics
- `GET /api/ollama/test` — Ollama diagnostics

### Auth Service

- `POST /register` — Register user
- `POST /signin` — Sign in (returns JWT)
- `GET /ping`, `GET /health`, `GET /metrics`

### Order Service

- `POST /api/v1/order` — Place order (JWT)
- `GET /api/v1/orders` — List user orders (JWT)
- `GET /ping`, `GET /health`, `GET /metrics`

### Catalog Service

- `POST /api/v1/add_product` — Add product (JWT)
- `POST /api/v1/update_stock` — Update stock (JWT)
- `GET /api/v1/product` — Search products (JWT)
- `GET /api/v1/all_products` — List all products (JWT)
- `GET /ping`, `GET /health`, `GET /metrics`

---

## 🔒 Security

- JWT-based authentication for all protected endpoints
- Secure password hashing (bcrypt)
- Service-to-service authentication
- Environment variable configuration

---

## 📝 Logging & Debugging

- All services log to `/app/logs/metrics.log` (mounted to `./logs`)
- View logs in real time via dashboard or `docker logs <service>`
- Prometheus logs: `docker logs prometheus`
- Debug endpoints: `/api/debug/*`

---

## 🤖 AI Root Cause Analysis

- `/api/root_cause` and dashboard button use Ollama LLaMA 3 for incident analysis
- Detects error spikes, latency anomalies, service-specific issues
- Returns actionable recommendations

---

## 🧪 Testing

- Controller generates traffic and errors
- Use `seed_catalog.py` to add products
- Manual API testing with curl/Postman

---

## ⚙️ Configuration

- `.env` for secrets and DB URIs
- `docker-compose.yaml` for service orchestration
- `prometheus/prometheus.yml` for metrics scraping

---

