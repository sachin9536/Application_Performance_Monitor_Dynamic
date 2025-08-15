# Dynamic Service Monitoring

A lightweight monitoring solution for any service that exposes Prometheus metrics. Easily register and monitor your services with a simple dashboard.

## Key Features

- **Dynamic Service Registration**
  - Monitor any service with a `/metrics` endpoint
  - Automatic service discovery
  - Simple API for registration

- **Basic Metrics Collection**
  - System metrics (CPU, memory)
  - HTTP request metrics
  - Custom application metrics

- **Simple Dashboard**
  - Service status overview
  - Basic metrics visualization
  - Log viewer

## Architecture

```
┌───────────────────────────────────────────────────────┐
│                   Your Services                        │
│  ─ Any language / framework                            │
│  ─ Just expose /metrics endpoint                       │
└───────────────▲───────────────────────────────────────┘
                │
                │ Prometheus scrape (HTTP pull)
                │
┌───────────────┴─────────────────┐
│ Monitoring Platform              │
│  ├─ FastAPI Backend               │
│  │   - Service registration API   │
│  │   - Metrics scraping logic     │
│  │   - Data processing & alerts   │
│  ├─ React Dashboard               │
│      - Service status overview    │
│      - Charts & logs              │
└───────────────┬──────────────────┘
                │
                ▼
┌─────────────────────────────┐
│ Data Storage                 │
│  - MongoDB                   │
│  - Optional AI models (Ollama,groq)│
└─────────────────────────────┘

```

### How It Works
1. **Service Registration**
   - Services register via API
   - Each service must expose a `/metrics` endpoint

2. **Metrics Collection**
   - The monitoring engine scrapes metrics
   - Data is stored in MongoDB

3. **Dashboard**
   - View service status
   - Basic metrics visualization

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.8+
- Node.js 16+ (for frontend development)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Application_Performance_Monitor_Dynamic-master
   ```

2. **Start the services**
   ```bash
   docker-compose up -d
   ```

3. **Access the dashboard**
   - Open http://localhost:8080 in your browser

### Register a Service

1. **Expose metrics** in your service (example for Node.js with prom-client):
   ```javascript
   const express = require('express');
   const client = require('prom-client');
   
   const app = express();
   const register = new client.Registry();
   
   // Add default metrics
   client.collectDefaultMetrics({ register });
   
   // Add a custom metric
   const httpRequestCounter = new client.Counter({
     name: 'http_requests_total',
     help: 'Total HTTP requests',
     labelNames: ['method', 'endpoint', 'status']
   });
   register.registerMetric(httpRequestCounter);
   
   // Expose metrics endpoint
   app.get('/metrics', async (req, res) => {
     res.set('Content-Type', register.contentType);
     res.end(await register.metrics());
   });
   
   app.listen(3000);
   ```

2. **Register your service** with the monitoring platform:
   ```bash
   curl -X POST http://localhost:8080/api/services/register \
     -H "Content-Type: application/json" \
     -d '{"name": "my-service", "url": "http://your-service:3000"}'
   ```

## Supported Metrics

The platform automatically collects standard Prometheus metrics from your services:

### System Metrics
- `process_cpu_seconds_total` - CPU usage
- `process_resident_memory_bytes` - Memory usage
- `process_open_fds` - Open file descriptors
- `process_start_time_seconds` - Process start time

### HTTP Metrics
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request duration histogram
- `http_request_size_bytes` - Request size
- `http_response_size_bytes` - Response size

### Custom Metrics
You can add any custom metrics using the Prometheus client library for your language

## Configuration

Environment variables in `.env`:
```
# MongoDB
MONGO_URI=mongodb://mongodb:27017/monitoring

# Prometheus
PROMETHEUS_URL=http://prometheus:9090

# Optional: Ollama for AI features
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3

# Optional: Email alerts
SENDGRID_API_KEY=your-sendgrid-key
ALERT_EMAIL_FROM=alerts@example.com
ALERT_EMAIL_TO=admin@example.com
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
