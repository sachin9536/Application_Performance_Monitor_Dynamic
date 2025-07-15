import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiService, dataUtils } from "../services/api";
import {
  ServerIcon,
  ArrowLeftIcon,
  ExclamationTriangleIcon,
  CpuChipIcon,
  ChartBarIcon,
  ClockIcon,
  DocumentTextIcon,
} from "@heroicons/react/24/outline";
import StatusBadge from "../components/StatusBadge";
import MetricCard from "../components/MetricCard";
import toast from "react-hot-toast";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const ServiceDetails = () => {
  const { name } = useParams();
  const navigate = useNavigate();
  const [service, setService] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("1h");
  const [apmMetrics, setApmMetrics] = useState(null);
  const [apmLoading, setApmLoading] = useState(false);
  const [debugInfo, setDebugInfo] = useState("");
  const [cpuHistory, setCpuHistory] = useState([]);
  const [memoryHistory, setMemoryHistory] = useState([]);
  const [loadForecast, setLoadForecast] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [endpointStatus, setEndpointStatus] = useState([]);
  // New state for dynamic endpoints
  const [endpoints, setEndpoints] = useState([]);
  const [newEndpoint, setNewEndpoint] = useState({ path: "", desc: "" });

  useEffect(() => {
    const fetchDetails = async () => {
      setLoading(true);
      setDebugInfo("");
      try {
        // Try registered services first (since Alpha, Beta, Gamma are registered)
        const reg = await apiService.getRegisteredServices();
        const regFound = reg.registered_services?.find((s) => s.name === name);
        if (regFound) {
          setService({ ...regFound, type: "registered" });
          setDebugInfo(`Found registered service: ${name}`);
          console.log("Loaded registered service:", regFound);
        } else {
          // Try core services as fallback
          const res = await apiService.getServices();
          const found = res.services?.find(
            (s) => s.name === name || s.displayName === name
          );
          if (found) {
            setService({ ...found, type: "core" });
            setDebugInfo(`Found core service: ${name}`);
            console.log("Loaded core service:", found);
          } else {
            setService(null);
            setDebugInfo(`Service not found: ${name}`);
          }
        }
      } catch (e) {
        setService(null);
        setDebugInfo(`Error fetching service: ${e.message}`);
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [name]);

  // Set endpoints from service
  useEffect(() => {
    if (service && service.endpoints) {
      setEndpoints(service.endpoints);
      console.log("Setting endpoints from service:", service.endpoints);
    }
  }, [service]);

  // Add endpoint handler
  const handleAddEndpoint = async () => {
    if (!newEndpoint.path.trim()) return;
    const updated = [...endpoints, { ...newEndpoint }];
    await apiService.addOrUpdateServiceEndpoints(service.name, updated);
    setEndpoints(updated);
    setNewEndpoint({ path: "", desc: "" });
  };

  // Delete endpoint handler
  const handleDeleteEndpoint = async (path) => {
    await apiService.deleteServiceEndpoint(service.name, path);
    setEndpoints(endpoints.filter((ep) => ep.path !== path));
  };

  // Fetch APM metrics for registered services
  useEffect(() => {
    if (!service || service.type !== "registered") {
      setDebugInfo(
        (prev) =>
          prev + ` | Skipping APM fetch: service type is ${service?.type}`
      );
      return;
    }

    setApmLoading(true);
    setDebugInfo(
      (prev) => prev + ` | Fetching APM metrics for ${service.name}`
    );

    apiService
      .getServiceMetrics(service.name, timeRange)
      .then((data) => {
        setApmMetrics(data.metrics);
        setDebugInfo(
          (prev) =>
            prev +
            ` | APM data received: ${
              Object.keys(data.metrics || {}).length
            } metrics`
        );
      })
      .catch((error) => {
        setApmMetrics(null);
        setDebugInfo((prev) => prev + ` | APM fetch failed: ${error.message}`);
      })
      .finally(() => setApmLoading(false));
  }, [service, timeRange]);

  // Fetch historical CPU and memory data for registered services
  useEffect(() => {
    if (!service || service.type !== "registered") {
      return;
    }

    setHistoryLoading(true);

    // Fetch CPU history
    apiService
      .getServiceCpuHistory(service.name, timeRange)
      .then((data) => {
        setCpuHistory(data.data || []);
      })
      .catch((error) => {
        console.error("Error fetching CPU history:", error);
        setCpuHistory([]);
      });

    // Fetch memory history
    apiService
      .getServiceMemoryHistory(service.name, timeRange)
      .then((data) => {
        setMemoryHistory(data.data || []);
      })
      .catch((error) => {
        console.error("Error fetching memory history:", error);
        setMemoryHistory([]);
      });

    // Fetch load forecast
    apiService
      .getServiceLoadForecast(service.name, 24)
      .then((data) => {
        setLoadForecast(data);
      })
      .catch((error) => {
        console.error("Error fetching load forecast:", error);
        setLoadForecast(null);
      })
      .finally(() => setHistoryLoading(false));
  }, [service, timeRange]);

  // Endpoint status checker (only for registered user services)
  useEffect(() => {
    const checkEndpoints = async () => {
      if (!service || service.type !== "registered" || !service.url) {
        setEndpointStatus([]);
        return;
      }
      const baseUrl = service.url
        .replace(/\/$/, "")
        .replace("host.docker.internal", "localhost");
      const results = await Promise.all(
        endpoints.map(async (ep) => {
          const url = baseUrl + ep.path;
          const start = Date.now();
          try {
            const res = await fetch(url, { method: "GET" });
            const time = Date.now() - start;
            return {
              ...ep,
              status: res.ok ? "up" : "down",
              responseTime: time,
              lastChecked: new Date(),
            };
          } catch {
            return {
              ...ep,
              status: "down",
              responseTime: null,
              lastChecked: new Date(),
            };
          }
        })
      );
      setEndpointStatus(results);
    };
    checkEndpoints();
    // Optionally, add a timer for periodic refresh
    // eslint-disable-next-line
  }, [service, endpoints]);

  if (loading)
    return (
      <div className="flex items-center justify-center h-64">Loading...</div>
    );
  if (!service)
    return (
      <div className="flex flex-col items-center justify-center h-64 text-danger-600">
        <div>Service not found</div>
      </div>
    );

  // Metrics helpers
  const getMetric = (val, suffix = "", decimals = 2) =>
    val !== undefined && val !== null ? (
      `${Number(val).toFixed(decimals)}${suffix}`
    ) : (
      <span className="text-gray-400">N/A</span>
    );

  const isDown = service.status !== "healthy" && service.status !== "warning";
  const statusLabel = isDown ? "DOWN" : "UP";
  const statusColor = isDown
    ? "bg-danger-100 text-danger-700"
    : "bg-success-100 text-success-700";

  // Real metrics
  const metrics = service.metrics || {};
  const avgLatencyMs = metrics.avg_latency ? metrics.avg_latency * 1000 : null;
  const errorRate =
    metrics.errors_total &&
    metrics.http_requests_total &&
    Number(metrics.http_requests_total) > 0
      ? ((metrics.errors_total / metrics.http_requests_total) * 100).toFixed(2)
      : null;

  // --- Empty State for No APM Data ---
  const hasApmData = apmMetrics && Object.keys(apmMetrics).length > 0;

  return (
    <div className="max-w-4xl mx-auto py-10 px-4 animate-fadeIn">
      {/* Header Card with Glass Effect */}
      <div className="relative mb-10">
        <div
          className="absolute inset-0 rounded-3xl bg-gradient-to-tr from-primary-50/80 to-white/80 shadow-xl blur-sm"
          style={{ zIndex: 0 }}
        />
        <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-6 bg-white/80 rounded-3xl shadow-lg border border-gray-100 px-8 py-8 backdrop-blur-md">
          <div className="flex-1 text-center md:text-left">
            <div className="flex items-center justify-center md:justify-start gap-4 mb-2">
              <span className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-primary-100 shadow-md">
                <ServerIcon className="w-8 h-8 text-primary-500" />
              </span>
              <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight">
                {service.displayName || service.name}
              </h1>
            </div>
            <div className="text-xs text-gray-500 font-mono truncate mb-1">
              {service.url || service.endpoint || "-"}
            </div>
            <div className="text-xs text-gray-400">
              As of {dataUtils.formatTimestamp(Date.now())}
            </div>
          </div>
          <div className="flex flex-col md:flex-row gap-3 items-center">
            <button
              className="btn btn-success flex items-center gap-2 px-7 py-3 text-base font-semibold rounded-full shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200"
              onClick={() =>
                navigate(`/metrics?service=${encodeURIComponent(service.name)}`)
              }
            >
              <ChartBarIcon className="w-5 h-5" />
              Start Monitoring
            </button>
            <button
              className="btn btn-primary flex items-center gap-2 px-7 py-3 text-base font-semibold rounded-full shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200"
              onClick={() =>
                navigate(`/logs?service=${encodeURIComponent(service.name)}`)
              }
            >
              <DocumentTextIcon className="w-5 h-5" />
              View Logs
            </button>
            <button
              className="btn btn-secondary flex items-center gap-2 px-7 py-3 text-base font-semibold rounded-full shadow hover:shadow-md hover:scale-105 transition-all duration-200"
              onClick={() => navigate(-1)}
            >
              <ArrowLeftIcon className="w-5 h-5" />
              Back
            </button>
          </div>
        </div>
      </div>

      {/* Main Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
        {/* Status Card */}
        <div
          className={`rounded-2xl shadow-lg border border-gray-100 p-8 flex flex-col min-h-[220px] bg-gradient-to-br ${
            isDown ? "from-red-50 to-white" : "from-green-50 to-white"
          }`}
        >
          <div className="flex items-center justify-between mb-4">
            <span className="font-bold text-lg tracking-wide text-gray-700">
              STATUS
            </span>
            <span
              className={`inline-flex items-center px-4 py-1.5 rounded-full text-sm font-bold uppercase ${statusColor} shadow`}
            >
              {statusLabel}
            </span>
          </div>
          <div className="space-y-4 mt-2 text-gray-700 text-lg">
            <div className="flex items-center">
              <ClockIcon className="w-5 h-5 mr-3 text-primary-400" />
              <span className="font-medium">Last Check:</span>
              <span className="ml-2 text-base font-mono">
                {service.last_scraped
                  ? dataUtils.formatTimestamp(service.last_scraped * 1000)
                  : "N/A"}
              </span>
            </div>
            <div className="flex items-center">
              <ChartBarIcon className="w-5 h-5 mr-3 text-primary-400" />
              <span className="font-medium">Response Time:</span>
              <span className="ml-2 text-base font-mono">
                {getMetric(avgLatencyMs, " ms")}
              </span>
            </div>
            <div className="flex items-center">
              <DocumentTextIcon className="w-5 h-5 mr-3 text-primary-400" />
              <span className="font-medium">HTTP Status:</span>
              <span className="ml-2 text-base font-mono">200</span>
            </div>
          </div>
        </div>
        {/* System Metrics Card */}
        <div className="rounded-2xl shadow-lg border border-gray-100 p-8 flex flex-col min-h-[220px] bg-gradient-to-br from-blue-50 to-white">
          <div className="font-bold text-lg mb-4 tracking-wide text-gray-700">
            SYSTEM METRICS
          </div>
          <div className="space-y-4 mt-2 text-gray-700 text-lg">
            <div className="flex items-center justify-between">
              <span className="flex items-center">
                <CpuChipIcon className="w-5 h-5 mr-3 text-blue-400" />
                <span className="font-medium">CPU Usage:</span>
              </span>
              <span className="font-bold text-xl font-mono">
                {getMetric(metrics.cpu_percent, "%")}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center">
                <CpuChipIcon className="w-5 h-5 mr-3 text-green-400" />
                <span className="font-medium">Memory Usage:</span>
              </span>
              <span className="font-bold text-xl font-mono">
                {getMetric(metrics.memory_used_mb, " MB")}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center">
                <ChartBarIcon className="w-5 h-5 mr-3 text-primary-400" />
                <span className="font-medium">Total Requests:</span>
              </span>
              <span className="font-bold text-xl font-mono">
                {getMetric(metrics.http_requests_total)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center">
                <ExclamationTriangleIcon className="w-5 h-5 mr-3 text-red-400" />
                <span className="font-medium">Errors:</span>
              </span>
              <span className="font-bold text-xl font-mono">
                {getMetric(metrics.errors_total)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center">
                <ChartBarIcon className="w-5 h-5 mr-3 text-yellow-400" />
                <span className="font-medium">Error Rate:</span>
              </span>
              <span className="font-bold text-xl font-mono">
                {errorRate !== null ? (
                  `${errorRate}%`
                ) : (
                  <span className="text-gray-400">N/A</span>
                )}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="h-8" />

      {/* Time Range Selector */}
      <div className="mb-8 flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">
          Performance Metrics
        </h2>
        <select
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-primary-500 shadow-sm"
        >
          <option value="1h">Last Hour</option>
          <option value="6h">Last 6 Hours</option>
          <option value="24h">Last 24 Hours</option>
          <option value="7d">Last 7 Days</option>
        </select>
      </div>

      {/* CPU and Memory Usage Graphs or Empty State */}
      {cpuHistory.length > 0 || memoryHistory.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
          {/* CPU Usage Graph */}
          <div className="bg-white rounded-2xl shadow-md border border-gray-100 p-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <CpuChipIcon className="w-6 h-6 text-blue-600" />
                CPU Usage
              </h3>
              {historyLoading && (
                <div className="text-sm text-gray-500">Loading...</div>
              )}
            </div>
            <div className="h-64">
              {cpuHistory.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={cpuHistory}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="time"
                      tickFormatter={(value) =>
                        new Date(value).toLocaleTimeString()
                      }
                      fontSize={14}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tickFormatter={(value) => `${value}%`}
                      fontSize={14}
                    />
                    <Tooltip
                      labelFormatter={(value) =>
                        new Date(value).toLocaleString()
                      }
                      formatter={(value) => [`${value}%`, "CPU Usage"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="cpu_percent"
                      stroke="#3b82f6"
                      strokeWidth={3}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-400 text-lg">
                  {historyLoading
                    ? "Loading CPU data..."
                    : "No CPU data available"}
                </div>
              )}
            </div>
          </div>

          {/* Memory Usage Graph */}
          <div className="bg-white rounded-2xl shadow-md border border-gray-100 p-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <CpuChipIcon className="w-6 h-6 text-green-600" />
                Memory Usage
              </h3>
              {historyLoading && (
                <div className="text-sm text-gray-500">Loading...</div>
              )}
            </div>
            <div className="h-64">
              {memoryHistory.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={memoryHistory}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="time"
                      tickFormatter={(value) =>
                        new Date(value).toLocaleTimeString()
                      }
                      fontSize={14}
                    />
                    <YAxis
                      domain={[0, "auto"]}
                      tickFormatter={(value) => `${value} MB`}
                      fontSize={14}
                    />
                    <Tooltip
                      labelFormatter={(value) =>
                        new Date(value).toLocaleString()
                      }
                      formatter={(value) => [`${value} MB`, "Memory Usage"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="memory_mb"
                      stroke="#22c55e"
                      strokeWidth={3}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-400 text-lg">
                  {historyLoading
                    ? "Loading memory data..."
                    : "No memory data available"}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center h-72 bg-white rounded-2xl shadow-inner border border-gray-100 mt-8 mb-12">
          <CpuChipIcon className="w-20 h-20 text-primary-200 mb-4" />
          <h3 className="text-2xl font-bold text-gray-700 mb-2">
            No Performance Data
          </h3>
          <p className="text-gray-500 max-w-md text-center text-lg">
            We couldn't find any APM metrics for this service in the selected
            time range.
            <br />
            Try changing the time range or check if the service is exposing
            Prometheus metrics correctly.
          </p>
        </div>
      )}

      {/* API Endpoint Status Section (for user-registered services) */}
      {service && service.type === "registered" && (
        <div className="bg-white rounded-xl shadow-md border border-gray-100 p-6 mb-8">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            API Endpoint Status
          </h3>
          {/* Summary Bar */}
          <div className="flex items-center gap-6 mb-4 text-sm font-medium">
            <span>Total APIs: {endpointStatus.length}</span>
            <span className="text-green-600">
              APIs Up: {endpointStatus.filter((a) => a.status === "up").length}
            </span>
            <span className="text-red-600">
              APIs Down:{" "}
              {endpointStatus.filter((a) => a.status === "down").length}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {endpointStatus.map((api) => (
              <div
                key={api.path}
                className={`border rounded-lg p-4 bg-white shadow flex flex-col gap-2 ${
                  api.status === "up"
                    ? "border-green-300"
                    : "border-red-300 bg-red-50"
                }`}
              >
                <div className="font-mono text-base font-semibold mb-1">
                  {api.path}
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`font-bold text-sm ${
                      api.status === "up" ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    ● {api.status === "up" ? "Up" : "Down"}
                  </span>
                </div>
                <div className="text-sm">
                  Response Time:{" "}
                  {api.responseTime !== null ? `${api.responseTime} ms` : "N/A"}
                </div>
                <div className="text-xs text-gray-500">
                  Last Checked: {api.lastChecked?.toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* API Endpoints Management (only for registered services) */}
      {service && service.type === "registered" && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-2">API Endpoints</h3>
          <ul className="mb-4">
            {endpoints.map((ep) => (
              <li key={ep.path} className="flex items-center gap-2 mb-1">
                <span className="font-mono">{ep.path}</span>
                <span className="text-gray-500 text-sm">{ep.desc}</span>
                <button
                  className="text-red-500 ml-2"
                  onClick={() => handleDeleteEndpoint(ep.path)}
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <input
              className="input"
              placeholder="/new-endpoint"
              value={newEndpoint.path}
              onChange={(e) =>
                setNewEndpoint((ep) => ({ ...ep, path: e.target.value }))
              }
            />
            <input
              className="input"
              placeholder="Description"
              value={newEndpoint.desc}
              onChange={(e) =>
                setNewEndpoint((ep) => ({ ...ep, desc: e.target.value }))
              }
            />
            <button className="btn btn-primary" onClick={handleAddEndpoint}>
              Add
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ServiceDetails;
