require("dotenv").config();
const express = require("express");
const mongoose = require("mongoose");
const cors = require("cors");
const client = require("prom-client");

const app = express();
const PORT = process.env.PORT || 4003;
const SERVICE_NAME = process.env.SERVICE_NAME || "Ereadz1";

app.use(cors());
app.use(express.json());

// --- AppVital Log Shipper Setup ---
const AppVitalLogShipper = require("./log_shipper"); // Make sure log_shipper.js is in the same directory
const logger = new AppVitalLogShipper({
  apiUrl: "http://localhost:8000", // Use 8001 for demo mode
  serviceName: SERVICE_NAME,
  batchSize: 5,
  flushInterval: 3000,
});

// Log server startup
logger.info("Server starting up", { port: PORT, service: SERVICE_NAME });

// --- Prometheus metrics setup ---
const collectDefaultMetrics = client.collectDefaultMetrics;
collectDefaultMetrics({ labels: { service: SERVICE_NAME } });

const httpRequestCounter = new client.Counter({
  name: "http_requests_total",
  help: "Total number of HTTP requests",
  labelNames: ["service", "method", "route", "status"],
});

// Add error counter for tracking 4xx and 5xx errors
const httpErrorCounter = new client.Counter({
  name: "http_errors_total",
  help: "Total number of HTTP errors (4xx and 5xx)",
  labelNames: ["service", "method", "route", "status", "error_type"],
});

// Add this after your httpErrorCounter.inc(...)
const errorsTotal = new client.Counter({
  name: "errors_total",
  help: "Total errors (for compatibility with AppVital backend)",
  labelNames: ["service"],
});

const httpRequestDuration = new client.Histogram({
  name: "http_request_duration_seconds",
  help: "Duration of HTTP requests in seconds",
  labelNames: ["service", "method", "route", "status"],
  buckets: [0.1, 0.5, 1, 2, 5],
});

const httpRequestDurationMs = new client.Histogram({
  name: "total_response_ms",
  help: "Duration of HTTP requests in milliseconds",
  labelNames: ["service", "method", "route", "status"],
  buckets: [10, 50, 100, 200, 500, 1000, 2000, 5000],
});

const totalResponseMsSimple = new client.Histogram({
  name: "total_response_ms_simple",
  help: "Total response time in ms (AppVital compatible)",
  labelNames: ["service"],
  buckets: [10, 50, 100, 200, 500, 1000, 2000, 5000],
});

const memoryUsedMb = new client.Gauge({
  name: "memory_used_mb",
  help: "Memory usage in MB",
  labelNames: ["service"],
});
const cpuPercent = new client.Gauge({
  name: "cpu_percent",
  help: "CPU usage percent",
  labelNames: ["service"],
});

let lastCpuUsage = process.cpuUsage();
let lastHrTime = process.hrtime();

setInterval(() => {
  // Memory calculation
  const mem = process.memoryUsage().rss / 1024 / 1024;
  memoryUsedMb.set({ service: SERVICE_NAME }, mem);

  // CPU calculation
  const currentCpuUsage = process.cpuUsage(lastCpuUsage);
  const currentHrTime = process.hrtime(lastHrTime);
  const elapsedMicros = currentHrTime[0] * 1e6 + currentHrTime[1] / 1e3;
  const totalCpuMicros = currentCpuUsage.user + currentCpuUsage.system;
  const cpuPercentValue = (totalCpuMicros / elapsedMicros) * 100;
  cpuPercent.set({ service: SERVICE_NAME }, cpuPercentValue);
  lastCpuUsage = process.cpuUsage();
  lastHrTime = process.hrtime();
}, 5000);

// Middleware to count requests and record durations
app.use((req, res, next) => {
  const startTime = Date.now();
  const labels = {
    service: SERVICE_NAME,
    method: req.method,
    route: req.path,
  };
  const end = httpRequestDuration.startTimer(labels);
  const endMs = httpRequestDurationMs.startTimer(labels);

  // Log service identification headers
  const requestingService = req.headers["x-requesting-service"] || "unknown";
  const targetService = req.headers["x-target-service"] || "unknown";
  const requestId = req.headers["x-request-id"] || "unknown";

  // Log the service request using the new method
  logger.logServiceRequest(requestingService, targetService, requestId, {
    method: req.method,
    path: req.path,
    user_agent: req.get("User-Agent"),
    ip: req.ip,
  });

  res.on("finish", () => {
    const status = res.statusCode;
    const duration = Date.now() - startTime;

    httpRequestCounter.inc({ ...labels, status });

    // Track errors separately
    if (status >= 400) {
      const errorType = status >= 500 ? "server_error" : "client_error";
      httpErrorCounter.inc({ ...labels, status, error_type: errorType });

      // Increment errors_total for every error
      errorsTotal.inc({ service: SERVICE_NAME });

      // Log errors to AppVital
      logger.error(`HTTP ${status} error`, {
        method: req.method,
        path: req.path,
        status: status,
        duration: duration,
        error_type: errorType,
        user_agent: req.get("User-Agent"),
        ip: req.ip,
        requesting_service: requestingService,
        target_service: targetService,
        request_id: requestId,
      });
    } else {
      // Log successful requests (optional - you can remove this if too verbose)
      logger.info(`HTTP ${status} request`, {
        method: req.method,
        path: req.path,
        status: status,
        duration: duration,
        user_agent: req.get("User-Agent"),
        ip: req.ip,
        requesting_service: requestingService,
        target_service: targetService,
        request_id: requestId,
      });
    }

    end({ status });
    endMs({ status });
  });
  next();
});

// --- /metrics endpoint ---
app.get("/metrics", async (req, res) => {
  res.set("Content-Type", client.register.contentType);
  res.end(await client.register.metrics());
});
// ------------------------

mongoose
  .connect(process.env.MONGODB_URI)
  .then(() => {
    console.log("Connected to MongoDB");
    logger.info("MongoDB connection established");
  })
  .catch((err) => {
    console.error("MongoDB connection error:", err);
    logger.error("MongoDB connection failed", { error: err.message });
  });

app.get("/", (req, res) => {
  const requestingService = req.headers["x-requesting-service"] || "unknown";
  const targetService = req.headers["x-target-service"] || "unknown";
  const requestId = req.headers["x-request-id"] || "unknown";

  res.json({
    message: "Welcome to eReadz API",
    requested_by: requestingService,
    target_service: targetService,
    request_id: requestId,
  });
});

// Error simulation routes
app.get("/error/400", (req, res) => {
  logger.warn("Simulated 400 error triggered");
  res.status(400).json({ error: "Bad Request - Invalid parameters" });
});

app.get("/error/401", (req, res) => {
  logger.warn("Simulated 401 error triggered");
  res.status(401).json({ error: "Unauthorized - Authentication required" });
});

app.get("/error/403", (req, res) => {
  logger.warn("Simulated 403 error triggered");
  res.status(403).json({ error: "Forbidden - Access denied" });
});

app.get("/error/404", (req, res) => {
  logger.warn("Simulated 404 error triggered");
  res.status(404).json({ error: "Not Found - Resource not available" });
});

app.get("/error/500", (req, res) => {
  logger.error("Simulated 500 error triggered");
  res
    .status(500)
    .json({ error: "Internal Server Error - Something went wrong" });
});

app.get("/error/502", (req, res) => {
  logger.error("Simulated 502 error triggered");
  res.status(502).json({ error: "Bad Gateway - Upstream service unavailable" });
});

app.get("/error/503", (req, res) => {
  logger.error("Simulated 503 error triggered");
  res.status(503).json({ error: "Service Unavailable - Temporarily down" });
});

// Random error route (sometimes returns 200, sometimes 500)
app.get("/error/random", (req, res) => {
  const random = Math.random();
  if (random > 0.7) {
    logger.error("Random error occurred", { probability: random });
    res.status(500).json({ error: "Random server error occurred" });
  } else {
    logger.info("Random endpoint success", { probability: random });
    res.json({ message: "Random endpoint - success this time" });
  }
});

// Slow endpoint to simulate high latency
app.get("/slow", async (req, res) => {
  const delay = Math.random() * 3000 + 1000; // 1-4 seconds
  logger.warn("Slow endpoint called", { delay: delay });
  await new Promise((resolve) => setTimeout(resolve, delay));
  res.json({ message: `Slow response after ${delay}ms` });
});

// Health check endpoint
app.get("/health", (req, res) => {
  res.json({
    status: "healthy",
    service: SERVICE_NAME,
    timestamp: new Date().toISOString(),
  });
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
  logger.info("Server started successfully", {
    port: PORT,
    service: SERVICE_NAME,
    environment: process.env.NODE_ENV || "development",
  });
});

// Graceful shutdown
process.on("SIGINT", () => {
  logger.info("Server shutting down gracefully");
  logger.stop();
  process.exit(0);
});

process.on("SIGTERM", () => {
  logger.info("Server received SIGTERM, shutting down");
  logger.stop();
  process.exit(0);
});

// Handle uncaught exceptions
process.on("uncaughtException", (err) => {
  logger.error("Uncaught exception", { error: err.message, stack: err.stack });
  process.exit(1);
});

process.on("unhandledRejection", (reason, promise) => {
  logger.error("Unhandled rejection", { reason: reason, promise: promise });
  process.exit(1);
});
