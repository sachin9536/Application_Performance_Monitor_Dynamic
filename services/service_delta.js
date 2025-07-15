const express = require("express");
const client = require("prom-client");
const os = require("os");

const app = express();
const SERVICE_NAME = "service_delta";

// Create a Registry and metrics with service label
const register = new client.Registry();
register.setDefaultLabels({ service: SERVICE_NAME });

const requestCount = new client.Counter({
  name: "http_requests_total",
  help: "Total HTTP requests",
  labelNames: ["service", "status"],
  registers: [register],
});
const requestLatency = new client.Summary({
  name: "http_request_duration_seconds",
  help: "Request duration in seconds",
  labelNames: ["service"],
  registers: [register],
});
const memoryUsedMB = new client.Gauge({
  name: "memory_used_mb",
  help: "Memory usage in MB",
  labelNames: ["service"],
  registers: [register],
});
const cpuPercent = new client.Gauge({
  name: "cpu_percent",
  help: "CPU usage percent",
  labelNames: ["service"],
  registers: [register],
});
const errorsTotal = new client.Counter({
  name: "errors_total",
  help: "Total errors",
  labelNames: ["service"],
  registers: [register],
});
const up = new client.Gauge({
  name: "up",
  help: "Service up status (1=up, 0=down)",
  labelNames: ["service"],
  registers: [register],
});

// Set up metric on startup
up.labels(SERVICE_NAME).set(1);

// Update process metrics
function updateProcessMetrics() {
  const memMb = process.memoryUsage().rss / 1024 / 1024;
  memoryUsedMB.labels(SERVICE_NAME).set(memMb);
  // Node doesn't have a direct process CPU percent, so we use system load as a proxy
  const load = (os.loadavg()[0] / os.cpus().length) * 100;
  cpuPercent.labels(SERVICE_NAME).set(load);
}

// Main endpoint
app.get("/", (req, res) => {
  let statusCode = 200;
  const end = requestLatency.labels(SERVICE_NAME).startTimer();
  if (Math.random() < 0.1) {
    errorsTotal.labels(SERVICE_NAME).inc();
    statusCode = 500;
  }
  requestCount.labels(SERVICE_NAME, String(statusCode)).inc();
  updateProcessMetrics();
  setTimeout(() => {
    end();
    res.status(statusCode).json({ message: "Hello from service delta!" });
  }, Math.random() * 400 + 100);
});

// Metrics endpoint
app.get("/metrics", async (req, res) => {
  res.set("Content-Type", register.contentType);
  res.end(await register.metrics());
});

// Periodic self-traffic
if (process.env.SELF_TRAFFIC === "1") {
  console.log(
    "[service_delta] SELF_TRAFFIC enabled: starting periodic requests."
  );
  setInterval(() => {
    require("http").get("http://localhost:9400/");
  }, 5000);
} else {
  console.log(
    "[service_delta] SELF_TRAFFIC disabled: not starting periodic requests."
  );
}

const PORT = 9400;
app.listen(PORT, () => {
  console.log(`service_delta running on port ${PORT}`);
});
