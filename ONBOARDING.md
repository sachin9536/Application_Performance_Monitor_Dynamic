# AppVital Monitoring Platform – Client Onboarding Guide

Welcome to **AppVital** – your all-in-one Application Performance Monitoring (APM) platform! This guide will help you quickly integrate any of your services (in any language or environment) for real-time monitoring, analytics, and insights.

---

## 🚀 Quick Start: Two Modes

### **Production Mode (for Clients)**

- **Purpose:** Monitor your own services in any environment.
- **How to run:**
  ```sh
  docker compose up
  ```
- **What happens:** Only the monitoring platform (backend, Prometheus, frontend) runs. You register your own services via the dashboard. All registered services are stored per-user in MongoDB (not in a JSON file).
- **What you see:**
  - If no services are registered, the dashboard will show "No data yet" states.
  - As soon as you register a service (with a `/metrics` endpoint), AppVital will start monitoring it.

### **Demo Mode (for Testing/Sales/Development)**

- **Purpose:** See the platform in action with sample data, even if you have no real services yet.
- **How to run:**
  ```sh
  docker compose --profile demo up
  ```
- **What happens:**
  - The platform runs **plus** sample services (`service_alpha`, `service_beta`, `service_gamma`, `dummy_service`) and a traffic generator.
  - These demo services expose `/metrics` endpoints and generate realistic traffic and logs.
  - Demo services are automatically registered and traffic is generated automatically.
- **How to use:**
  1. Go to the dashboard at [http://localhost:3000](http://localhost:3000).
  2. Demo services are automatically registered and will appear in your Services page.
  3. The traffic generator will automatically generate logs and metrics for these services.
  4. You can also manually register additional services using their URLs:
     - `http://service_alpha:8000`
     - `http://service_beta:8000`
     - `http://service_gamma:8000`
     - `http://dummy_service:9000`

---

## 🛠️ Instrumenting Your Own Services (Production)

1. **Add Prometheus client library to your service** (any language):
   - [Python](https://github.com/prometheus/client_python)
   - [Node.js](https://github.com/siimon/prom-client)
   - [Go](https://github.com/prometheus/client_golang)
   - [Java](https://github.com/prometheus/client_java)
   - [.NET](https://github.com/prometheus-net/prometheus-net)
2. **Expose a `/metrics` endpoint** in your service.
3. **Register your service** in the AppVital dashboard (name + URL). Services are stored per-user in MongoDB.
4. **AppVital will automatically start monitoring and visualizing your metrics!**

---

## 🧑‍💻 Best Practices & Troubleshooting

- **No data?**
  - Make sure your service is running and `/metrics` is reachable from the monitoring platform.
  - Check that you registered the correct URL (including port).
- **Not using Docker?**
  - Your services do **not** need to run in Docker. Only the monitoring platform does.
- **Want to see sample data?**
  - Use demo mode as described above.
- **Need help instrumenting your service?**
  - See the [Prometheus docs](https://prometheus.io/docs/instrumenting/clientlibs/) or contact support.

---

## 💡 Summary

- **Production:** Only the platform runs; you register your own services.
- **Demo:** Platform + sample services + traffic generator for instant demo data.
- **No Docker required for your services!**

---

For more help, see the full documentation or contact support.
