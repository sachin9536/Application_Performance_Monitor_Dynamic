import axios from "axios";
import toast from "react-hot-toast";

// Create axios instance with base configuration
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000",
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error("API Request Error:", error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error("API Response Error:", error);

    const message =
      error.response?.data?.detail || error.message || "An error occurred";

    // Show toast notification for errors
    if (error.response?.status >= 500) {
      toast.error(`Server Error: ${message}`);
    } else if (error.response?.status >= 400) {
      toast.error(`Request Error: ${message}`);
    } else if (error.code === "ECONNABORTED") {
      toast.error("Request timeout. Please try again.");
    } else {
      toast.error(`Network Error: ${message}`);
    }

    return Promise.reject(error);
  }
);

// API endpoints
export const API_ENDPOINTS = {
  // Health & Status
  HEALTH: "/api/health",
  SUMMARY: "/api/summary",

  // Metrics & Analytics
  METRICS: "/api/metrics",
  PERFORMANCE: "/api/performance",
  ANALYTICS: "/api/analytics",

  // Logs
  LOGS: "/api/logs",

  // Error Analysis
  ERROR_ANALYSIS: "/api/errors/analysis",
  ROOT_CAUSE: "/api/root_cause",

  // Prometheus
  PROMETHEUS_STATUS: "/api/prometheus/status",

  // Ollama
  OLLAMA_TEST: "/api/ollama/test",
};

// API service functions
export const apiService = {
  // Health & Status
  async getHealth() {
    const response = await api.get(API_ENDPOINTS.HEALTH);
    return response.data;
  },

  async getSummary() {
    const response = await api.get(API_ENDPOINTS.SUMMARY);
    return response.data;
  },

  // Metrics & Analytics
  async getMetrics() {
    const response = await api.get(API_ENDPOINTS.METRICS);
    return response.data;
  },

  async getPerformance() {
    const response = await api.get(API_ENDPOINTS.PERFORMANCE);
    return response.data;
  },

  async getAnalytics() {
    const response = await api.get(API_ENDPOINTS.ANALYTICS);
    return response.data;
  },

  // Logs
  async getLogs(limit = 1000, offset = 0) {
    const response = await api.get(API_ENDPOINTS.LOGS, {
      params: { limit, offset },
    });
    return response.data;
  },

  // Error Analysis
  async getErrorAnalysis() {
    const response = await api.get(API_ENDPOINTS.ERROR_ANALYSIS);
    return response.data;
  },

  async getRootCause() {
    const response = await api.get(API_ENDPOINTS.ROOT_CAUSE);
    return response.data;
  },

  // Prometheus
  async getPrometheusStatus() {
    const response = await api.get(API_ENDPOINTS.PROMETHEUS_STATUS);
    return response.data;
  },

  // Ollama
  async testOllama() {
    const response = await api.get(API_ENDPOINTS.OLLAMA_TEST);
    return response.data;
  },

  // GROQ
  async testGroq() {
    const response = await api.get("/api/test_groq");
    return response.data;
  },

  // Prometheus direct queries (for advanced metrics)
  async queryPrometheus(query) {
    const response = await axios.get(`http://localhost:9090/api/v1/query`, {
      params: { query },
      timeout: 5000,
    });
    return response.data;
  },

  // Get Prometheus targets
  async getPrometheusTargets() {
    const response = await axios.get(`http://localhost:9090/api/v1/targets`, {
      timeout: 5000,
    });
    return response.data;
  },

  // Services
  async getServices() {
    const response = await api.get("/api/services");
    return response.data;
  },

  // Error Rate Time Series
  async getErrorRateTimeSeries(window = "24h", interval = "1h") {
    const response = await api.get("/api/metrics/error_rate_timeseries", {
      params: { window, interval },
    });
    return response.data;
  },

  // HTTP Requests Over Time
  async getHttpRequestsTimeSeries(window = "24h", interval = "1h") {
    const response = await api.get("/api/metrics/http_requests_timeseries", {
      params: { window, interval },
    });
    return response.data;
  },

  // Response Time Over Time
  async getResponseTimeTimeSeries(window = "24h", interval = "1h") {
    const response = await api.get("/api/metrics/response_time_timeseries", {
      params: { window, interval },
    });
    return response.data;
  },

  // CPU Usage Over Time
  async getCpuUsageTimeSeries(window = "24h", interval = "1h") {
    const response = await api.get("/api/metrics/cpu_usage_timeseries", {
      params: { window, interval },
    });
    return response.data;
  },

  // Memory Usage Over Time
  async getMemoryUsageTimeSeries(window = "24h", interval = "1h") {
    const response = await api.get("/api/metrics/memory_usage_timeseries", {
      params: { window, interval },
    });
    return response.data;
  },

  // Response Code Distribution
  async getResponseCodeDistribution(window = "24h") {
    const response = await api.get("/api/metrics/response_code_distribution", {
      params: { window },
    });
    return response.data;
  },

  // AI Log Summary (General)
  async getAiLogSummary(logCount = 200) {
    // Reduced back to 200 for faster processing
    const response = await api.get("/api/ai_analysis", {
      params: { log_count: logCount, mode: "summary" },
    });
    return response.data;
  },

  // AI Root Cause Analysis (Full RCA)
  async getAiRootCause(logCount = 30) {
    // Reduced to 30 for faster processing and to avoid LLM context issues
    const response = await api.get("/api/ai_analysis", {
      params: { log_count: logCount, mode: "root_cause" },
    });
    return response.data;
  },

  // Register a new service
  async registerService({ name, url }) {
    const response = await api.post("/api/services", { name, url });
    return response.data;
  },

  // Registered Services (new endpoints)
  async getRegisteredServices() {
    const response = await api.get("/api/registered_services");
    return response.data;
  },
  async registerRegisteredService({ name, url }) {
    const response = await api.post("/api/registered_services", { name, url });
    return response.data;
  },

  // Test a metrics endpoint before registration
  async testMetricsEndpoint(url) {
    const response = await api.get("/api/test_metrics_endpoint", {
      params: { url },
    });
    return response.data;
  },

  // Delete a registered service by name
  async deleteRegisteredService(name) {
    const response = await api.delete("/api/registered_services", {
      params: { name },
    });
    return response.data;
  },

  // Add or update endpoints for a registered service
  addOrUpdateServiceEndpoints: (serviceName, endpoints) =>
    api.post(`/api/registered_services/${serviceName}/endpoints`, endpoints),

  // Delete a specific endpoint for a registered service
  deleteServiceEndpoint: (serviceName, path) =>
    api.delete(
      `/api/registered_services/${serviceName}/endpoints?path=${encodeURIComponent(
        path
      )}`
    ),

  // System Overview
  async getSystemOverview() {
    const response = await api.get("/api/system_overview");
    return response.data;
  },

  // Fetch per-service time series metrics (APM)
  async getServiceMetrics(name, window = "1h") {
    const response = await api.get(`/api/service_metrics/${name}`, {
      params: { window },
    });
    return response.data;
  },

  async getServiceMetricsSummary(name) {
    const response = await api.get(`/api/service_metrics/${name}/summary`);
    return response.data;
  },

  // Database Management
  async getDatabases() {
    const response = await api.get("/api/databases");
    return response.data;
  },

  async addDatabase({ name, uri, type }) {
    const response = await api.post("/api/databases", { name, uri, type });
    return response.data;
  },

  async removeDatabase(name) {
    const response = await api.delete(`/api/databases`, { params: { name } });
    return response.data;
  },

  // Test database connection before saving
  async testDatabaseConnection({ type, uri }) {
    const response = await api.post("/api/databases/test_connection", {
      type,
      uri,
    });
    return response.data;
  },

  // User Authentication
  async registerUser({ email, password }) {
    const response = await api.post("/register", { email, password });
    return response.data;
  },

  async loginUser({ email, password }) {
    const response = await api.post("/login", { email, password });
    return response.data;
  },

  // Log Ingestion
  async ingestLogs(logs) {
    const response = await api.post("/api/ingest_log", { logs });
    return response.data;
  },

  async ingestSingleLog(logEntry) {
    const response = await api.post("/api/ingest_single_log", logEntry);
    return response.data;
  },

  // Per-service HTTP Requests Over Time
  async getServiceRequestsTimeSeries(name, window = "6h", interval = "5m") {
    const response = await api.get(
      `/api/service_metrics/${name}/requests_timeseries`,
      {
        params: { window, interval },
      }
    );
    return response.data;
  },

  // Per-service Response Time Over Time
  async getServiceResponseTimeTimeSeries(name, window = "6h", interval = "5m") {
    const response = await api.get(
      `/api/service_metrics/${name}/response_time_timeseries`,
      {
        params: { window, interval },
      }
    );
    return response.data;
  },

  // Per-service Errors Over Time
  async getServiceErrorsTimeSeries(name, window = "6h", interval = "5m") {
    const response = await api.get(
      `/api/service_metrics/${name}/errors_timeseries`,
      { params: { window, interval } }
    );
    return response.data;
  },

  // Per-service CPU History (NEW)
  async getServiceCpuHistory(name, window = "24h") {
    const response = await api.get(`/api/service_metrics/${name}/cpu_history`, {
      params: { window },
    });
    return response.data;
  },

  // Per-service Memory History (NEW)
  async getServiceMemoryHistory(name, window = "24h") {
    const response = await api.get(
      `/api/service_metrics/${name}/memory_history`,
      { params: { window } }
    );
    return response.data;
  },

  // Per-service Load Forecast (NEW)
  async getServiceLoadForecast(name, forecastHours = 24) {
    const response = await api.get(
      `/api/service_metrics/${name}/load_forecast`,
      { params: { forecast_hours: forecastHours } }
    );
    return response.data;
  },
};

// Utility functions for data processing
export const dataUtils = {
  // Format status for display
  formatStatus(status) {
    const statusMap = {
      healthy: { label: "Healthy", color: "success", icon: "✓" },
      unhealthy: { label: "Unhealthy", color: "error", icon: "✗" },
      warning: { label: "Warning", color: "warning", icon: "⚠" },
      unknown: { label: "Unknown", color: "gray", icon: "?" },
    };
    return statusMap[status] || statusMap.unknown;
  },

  // Format numbers for display
  formatNumber(num, decimals = 2) {
    if (num === null || num === undefined) return "N/A";
    if (typeof num === "string") return num;

    if (num >= 1000000) {
      return `${(num / 1000000).toFixed(decimals)}M`;
    } else if (num >= 1000) {
      return `${(num / 1000).toFixed(decimals)}K`;
    } else {
      return num.toFixed(decimals);
    }
  },

  // Format percentage
  formatPercentage(value, total) {
    if (!total || total === 0) return "0%";
    return `${((value / total) * 100).toFixed(1)}%`;
  },

  // Format duration
  formatDuration(seconds) {
    if (!seconds) return "N/A";

    if (seconds < 1) {
      return `${(seconds * 1000).toFixed(0)}ms`;
    } else if (seconds < 60) {
      return `${seconds.toFixed(2)}s`;
    } else {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
    }
  },

  // Get color for metric values
  getMetricColor(value, thresholds = { warning: 80, error: 95 }) {
    if (value >= thresholds.error) return "danger";
    if (value >= thresholds.warning) return "warning";
    return "success";
  },

  // Parse log level for styling
  getLogLevelColor(level) {
    const levelMap = {
      error: "danger",
      warning: "warning",
      info: "primary",
      debug: "gray",
    };
    return levelMap[level?.toLowerCase()] || "gray";
  },

  // Format timestamp for display
  formatTimestamp(timestamp) {
    if (!timestamp) return "N/A";

    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);

      if (diffMins < 1) {
        return "Just now";
      } else if (diffMins < 60) {
        return `${diffMins}m ago`;
      } else if (diffHours < 24) {
        return `${diffHours}h ago`;
      } else {
        return date.toLocaleString();
      }
    } catch (error) {
      return timestamp;
    }
  },
};

export default api;
export { api };
