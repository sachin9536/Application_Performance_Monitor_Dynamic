import React, { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { apiService, dataUtils } from "../services/api";
import {
  ChartBarIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  ServerIcon,
} from "@heroicons/react/24/outline";
import MetricCard from "../components/MetricCard";
import toast from "react-hot-toast";
import { useAuth } from "../AuthContext";
import { Tooltip as RechartsTooltip } from "recharts";
import { useLocation } from "react-router-dom";

const Metrics = () => {
  const location = useLocation();
  const [metrics, setMetrics] = useState(null);
  const [prometheusData, setPrometheusData] = useState(null);
  const [errorRateSeries, setErrorRateSeries] = useState([]);
  const [httpRequestsSeries, setHttpRequestsSeries] = useState([]);
  const [responseTimeSeries, setResponseTimeSeries] = useState([]);
  const [cpuUsageSeries, setCpuUsageSeries] = useState([]);
  const [memoryUsageSeries, setMemoryUsageSeries] = useState([]);
  const [responseCodeData, setResponseCodeData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [windowValue, setWindowValue] = useState("6h");
  const [intervalValue, setIntervalValue] = useState("5m");

  // New state for service-specific functionality
  const [registeredServices, setRegisteredServices] = useState([]);
  const [selectedService, setSelectedService] = useState("all");
  const [serviceMetrics, setServiceMetrics] = useState(null);
  const [serviceSummary, setServiceSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [serviceRequestsSeries, setServiceRequestsSeries] = useState([]);
  const [serviceResponseTimeSeries, setServiceResponseTimeSeries] = useState(
    []
  );
  const [serviceErrorsSeries, setServiceErrorsSeries] = useState([]);

  // Chart colors
  const colors = {
    primary: "#3b82f6",
    success: "#22c55e",
    warning: "#f59e0b",
    danger: "#ef4444",
    gray: "#6b7280",
  };

  const { logout } = useAuth();
  const [fetchError, setFetchError] = useState(null);

  // Handle URL parameters for service filtering
  useEffect(() => {
    const urlParams = new URLSearchParams(location.search);
    const serviceParam = urlParams.get("service");
    if (serviceParam && registeredServices.length > 0) {
      const serviceExists = registeredServices.find(
        (s) => s.name === serviceParam
      );
      if (serviceExists) {
        setSelectedService(serviceParam);
      }
    }
  }, [location.search, registeredServices]);

  // Fetch registered services with robust error handling
  const fetchRegisteredServices = async () => {
    setFetchError(null);
    try {
      const response = await apiService.getRegisteredServices();
      const services = response.registered_services || [];
      console.log("Fetched registered services (Metrics):", services);
      setRegisteredServices(services);

      // Check for service parameter in URL
      const urlParams = new URLSearchParams(location.search);
      const serviceParam = urlParams.get("service");

      if (serviceParam && services.find((s) => s.name === serviceParam)) {
        setSelectedService(serviceParam);
      } else if (
        services.length > 0 &&
        (selectedService === "all" || !selectedService)
      ) {
        setSelectedService(services[0].name);
      } else if (services.length === 0) {
        setSelectedService("all");
      }
    } catch (error) {
      console.error("Failed to fetch registered services (Metrics):", error);
      setRegisteredServices([]);
      if (
        error?.response?.status === 401 ||
        (error?.message &&
          error.message.toLowerCase().includes("not authenticated"))
      ) {
        setFetchError("You are not authenticated. Please log in again.");
        toast.error(
          "Session expired or not authenticated. Please log in again."
        );
      } else {
        setFetchError("Failed to fetch registered services. Please try again.");
        toast.error("Failed to fetch registered services.");
      }
    }
  };

  // Fetch metrics data with debug logging
  const fetchMetricsData = async () => {
    try {
      setLoading(true);
      setFetchError(null);
      console.log("Fetching metrics for:", selectedService);

      if (selectedService === "all") {
        // Fetch all services metrics (existing logic)
        const [
          metricsData,
          prometheusStatus,
          errorRateData,
          httpRequestsData,
          responseTimeData,
          cpuUsageData,
          memoryUsageData,
          responseCodeDist,
        ] = await Promise.all([
          apiService.getMetrics(),
          apiService.getPrometheusStatus(),
          apiService.getErrorRateTimeSeries(windowValue, intervalValue),
          apiService.getHttpRequestsTimeSeries(windowValue, intervalValue),
          apiService.getResponseTimeTimeSeries(windowValue, intervalValue),
          apiService.getCpuUsageTimeSeries(windowValue, intervalValue),
          apiService.getMemoryUsageTimeSeries(windowValue, intervalValue),
          apiService.getResponseCodeDistribution(windowValue),
        ]);

        setMetrics(metricsData);
        setPrometheusData(prometheusStatus);
        setServiceMetrics(null);

        // Format time series for charts (convert UTC to local time)
        setErrorRateSeries(
          errorRateData.map((d) => ({
            time: new Date(d.time * 1000).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            value: d.error_rate,
          }))
        );
        setHttpRequestsSeries(
          httpRequestsData.map((d) => ({
            time: new Date(d.time * 1000).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            value: d.total,
          }))
        );
        setResponseTimeSeries(
          responseTimeData.map((d) => ({
            time: new Date(d.time * 1000).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            value: d.avg_response_time_ms / 1000, // convert ms to s
          }))
        );
        setCpuUsageSeries(
          cpuUsageData.map((d) => ({
            time: new Date(d.time * 1000).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            value: d.cpu_percent,
          }))
        );
        setMemoryUsageSeries(
          memoryUsageData.map((d) => ({
            time: new Date(d.time * 1000).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            value: d.memory_mb,
          }))
        );
        // For 'All Services', aggregate response codes into Success and Error for the pie chart
        const successCount =
          (responseCodeDist["200"] || 0) +
          (responseCodeDist["201"] || 0) +
          (responseCodeDist["202"] || 0) +
          (responseCodeDist["204"] || 0);
        const errorCount =
          (responseCodeDist["400"] || 0) +
          (responseCodeDist["401"] || 0) +
          (responseCodeDist["403"] || 0) +
          (responseCodeDist["404"] || 0) +
          (responseCodeDist["500"] || 0) +
          (responseCodeDist["502"] || 0) +
          (responseCodeDist["503"] || 0);
        setResponseCodeData([
          {
            name: "Success",
            value: successCount,
            color: colors.success,
          },
          {
            name: "Error",
            value: errorCount,
            color: colors.danger,
          },
        ]);
      } else {
        // Fetch service-specific metrics
        const serviceData = await apiService.getServiceMetrics(
          selectedService,
          windowValue
        );
        setServiceMetrics(serviceData);
        setMetrics(null);
        setPrometheusData(null);

        // Format service-specific time series
        const formatServiceMetrics = (metricName) => {
          const metricData = serviceData.metrics?.[metricName] || [];
          return metricData.map((d) => ({
            time: new Date(d.timestamp * 1000).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            value: d.value,
          }));
        };

        setErrorRateSeries(formatServiceMetrics("errors_total"));
        setHttpRequestsSeries(formatServiceMetrics("http_requests_total"));
        setResponseTimeSeries(formatServiceMetrics("total_response_ms"));
        setCpuUsageSeries(formatServiceMetrics("cpu_percent"));
        setMemoryUsageSeries(formatServiceMetrics("memory_used_mb"));

        // For service-specific, we'll show a simplified response code distribution
        setResponseCodeData([
          {
            name: "Requests",
            value:
              serviceData.metrics?.http_requests_total?.[
                serviceData.metrics.http_requests_total.length - 1
              ]?.value || 0,
            color: colors.success,
          },
          {
            name: "Errors",
            value:
              serviceData.metrics?.errors_total?.[
                serviceData.metrics.errors_total.length - 1
              ]?.value || 0,
            color: colors.danger,
          },
        ]);
      }

      setLastUpdated(new Date());
    } catch (error) {
      console.error("Failed to fetch metrics:", error);
      setFetchError("Failed to load metrics data.");
      toast.error("Failed to load metrics data");
    } finally {
      setLoading(false);
    }
  };

  // Fetch registered services on mount
  useEffect(() => {
    fetchRegisteredServices();
  }, []);

  // Fetch metrics when service selection or time window changes
  useEffect(() => {
    if (registeredServices.length > 0 || selectedService === "all") {
      fetchMetricsData();
    }
  }, [selectedService, windowValue, intervalValue, registeredServices.length]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(fetchMetricsData, 30000);
    return () => clearInterval(interval);
  }, [selectedService, windowValue, intervalValue]);

  // Fetch per-service time series when service or window/interval changes
  useEffect(() => {
    if (selectedService !== "all") {
      apiService
        .getServiceRequestsTimeSeries(
          selectedService,
          windowValue,
          intervalValue
        )
        .then(setServiceRequestsSeries)
        .catch(() => setServiceRequestsSeries([]));
      apiService
        .getServiceResponseTimeTimeSeries(
          selectedService,
          windowValue,
          intervalValue
        )
        .then(setServiceResponseTimeSeries)
        .catch(() => setServiceResponseTimeSeries([]));
      apiService
        .getServiceErrorsTimeSeries(selectedService, windowValue, intervalValue)
        .then(setServiceErrorsSeries)
        .catch(() => setServiceErrorsSeries([]));
    } else {
      setServiceRequestsSeries([]);
      setServiceResponseTimeSeries([]);
      setServiceErrorsSeries([]);
    }
  }, [selectedService, windowValue, intervalValue]);

  // Fetch service summary when a specific service is selected
  useEffect(() => {
    if (selectedService !== "all") {
      setSummaryLoading(true);
      apiService
        .getServiceMetricsSummary(selectedService)
        .then((res) => {
          setServiceSummary(res);
        })
        .catch((err) => {
          setServiceSummary(null);
          if (err?.response?.status === 401) {
            setFetchError("You are not authenticated. Please log in again.");
            toast.error(
              "Session expired or not authenticated. Please log in again."
            );
          } else {
            setFetchError("Failed to fetch service summary. Please try again.");
            toast.error("Failed to fetch service summary.");
          }
        })
        .finally(() => setSummaryLoading(false));
    } else {
      setServiceSummary(null);
    }
  }, [selectedService]);

  // Service metrics cards (dynamic based on selected service)
  const getServiceMetricsCards = () => {
    if (selectedService === "all") {
      return [
        {
          title: "HTTP Requests",
          value: metrics?.log_metrics?.total || 0,
          subtitle: "Total requests",
          icon: ChartBarIcon,
          color: "primary",
        },
        {
          title: "Error Rate",
          value: `${(
            metrics?.log_metrics?.performance_metrics?.error_rate || 0
          ).toFixed(2)}%`,
          subtitle: "Last hour",
          icon: ExclamationTriangleIcon,
          color: "danger",
        },
        {
          title: "Avg Response Time",
          value: dataUtils.formatDuration(
            metrics?.log_metrics?.performance_metrics?.avg_latency_ms / 1000
          ),
          subtitle: "Request latency",
          icon: ClockIcon,
          color: "warning",
        },
        {
          title: "Active Services",
          value:
            prometheusData?.targets?.filter((t) => t.health === "up").length ||
            0,
          subtitle: "Healthy targets",
          icon: ChartBarIcon,
          color: "success",
        },
      ];
    } else {
      // Use serviceSummary for summary cards
      const status = serviceSummary?.status;
      let statusLabel = "Unknown";
      let statusColor = "gray";
      if (status === "healthy") {
        statusLabel = "Up";
        statusColor = "success";
      } else if (status === "warning") {
        statusLabel = "Warning";
        statusColor = "warning";
      } else if (status === "down" || status === "unhealthy") {
        statusLabel = "Down";
        statusColor = "danger";
      }
      return [
        {
          title: "HTTP Requests",
          value: summaryLoading
            ? "..."
            : serviceSummary?.total_requests ?? "N/A",
          subtitle: "Total requests",
          icon: ChartBarIcon,
          color: "primary",
        },
        {
          title: "Errors",
          value: summaryLoading ? "..." : serviceSummary?.errors ?? "N/A",
          subtitle: "Total errors",
          icon: ExclamationTriangleIcon,
          color: "danger",
        },
        {
          title: "Avg Response Time",
          value: summaryLoading
            ? "..."
            : serviceSummary?.avg_latency_ms !== undefined &&
              serviceSummary?.avg_latency_ms !== null
            ? `${serviceSummary.avg_latency_ms}ms`
            : "N/A",
          subtitle: "Avg latency",
          icon: ClockIcon,
          color: "warning",
        },
        {
          title: "Error Rate",
          value: summaryLoading
            ? "..."
            : serviceSummary?.error_rate !== undefined &&
              serviceSummary?.error_rate !== null
            ? `${serviceSummary.error_rate}%`
            : "N/A",
          subtitle: "Error rate",
          icon: ExclamationTriangleIcon,
          color: "danger",
        },
        {
          title: "Status",
          value: summaryLoading ? (
            "..."
          ) : (
            <span
              className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-bold uppercase bg-${statusColor}-100 text-${statusColor}-700`}
            >
              {statusLabel}
            </span>
          ),
          subtitle: "Current status",
          icon: ServerIcon,
          color: statusColor,
        },
      ];
    }
  };

  // Retry handler for auth errors
  const handleRetry = () => {
    logout();
    window.location.href = "/login";
  };

  // Format per-service data for charts
  const formattedRequestsSeries = (
    selectedService === "all" ? httpRequestsSeries : serviceRequestsSeries
  ).map((d) => ({
    ...d,
    // time is already formatted as a string, do not re-convert
    value: d.total !== undefined ? d.total : d.value,
  }));
  const formattedResponseTimeSeries = (
    selectedService === "all" ? responseTimeSeries : serviceResponseTimeSeries
  ).map((d) => ({
    ...d,
    value: d.avg_response_time_ms || d.value,
  }));
  const formattedErrorsSeries = (
    selectedService === "all" ? errorRateSeries : serviceErrorsSeries
  ).map((d) => ({
    ...d,
    value: d.errors !== undefined ? d.errors : d.value,
  }));

  // For per-service request summary pie chart (sum over window)
  let requestSummaryData = [];
  if (selectedService !== "all") {
    // Sum over all buckets in the window
    const totalRequests = serviceRequestsSeries.reduce(
      (sum, d) => sum + (d.total || 0),
      0
    );
    const totalErrors = serviceErrorsSeries.reduce(
      (sum, d) => sum + (d.errors || 0),
      0
    );
    const totalSuccess = Math.max(totalRequests - totalErrors, 0);
    requestSummaryData = [
      { name: "Success", value: totalSuccess, color: colors.success },
      { name: "Errors", value: totalErrors, color: colors.danger },
    ];
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {fetchError && (
        <div className="bg-danger-50 border border-danger-200 text-danger-800 rounded-lg p-4 flex items-center justify-between">
          <span>{fetchError}</span>
          <button className="btn btn-danger ml-4" onClick={handleRetry}>
            {fetchError.toLowerCase().includes("not authenticated")
              ? "Log in again"
              : "Retry"}
          </button>
        </div>
      )}
      {/* Header */}
      <div className="flex items-center justify-between bg-white/80 backdrop-blur-xs rounded-xl shadow-sm px-6 py-4 mb-4 border border-gray-100">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-1">
            Metrics & Analytics
          </h1>
          <p className="text-lg text-gray-600">
            {selectedService === "all"
              ? "All Services"
              : `${selectedService} Service`}{" "}
            - Prometheus metrics and performance data
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-base text-gray-500">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
          <button
            onClick={fetchMetricsData}
            disabled={loading}
            className="btn btn-primary shadow-md hover:scale-105 transition-transform"
          >
            <ArrowPathIcon
              className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`}
            />
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Service Selector & Time Controls */}
      <div className="flex flex-wrap items-center gap-4 mb-2">
        {/* Service Selector */}
        <div className="relative">
          <label className="text-sm font-medium text-gray-700 mr-2">
            Service:
          </label>
          <select
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            className="input rounded-lg border border-primary-200 focus:ring-2 focus:ring-primary-400 focus:border-primary-400 shadow-sm px-3 py-2 bg-white text-gray-900 transition-all duration-150 hover:border-primary-400"
            disabled={registeredServices.length === 0}
          >
            {registeredServices.length === 0 ? (
              <option value="all">No services registered</option>
            ) : (
              <>
                <option value="all">All Services</option>
                {registeredServices.map((service) => (
                  <option key={service.name} value={service.name}>
                    {service.name}
                  </option>
                ))}
              </>
            )}
          </select>
        </div>

        {/* Time Window Selector */}
        <div className="relative">
          <label className="text-sm font-medium text-gray-700 mr-2">
            Time Window:
          </label>
          <select
            value={windowValue}
            onChange={(e) => setWindowValue(e.target.value)}
            className="input rounded-lg border border-primary-200 focus:ring-2 focus:ring-primary-400 focus:border-primary-400 shadow-sm px-3 py-2 bg-white text-gray-900 transition-all duration-150 hover:border-primary-400"
          >
            <option value="1h">Last 1 hour</option>
            <option value="6h">Last 6 hours</option>
            <option value="12h">Last 12 hours</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
          </select>
        </div>

        {/* Interval Selector */}
        <div className="relative">
          <label className="text-sm font-medium text-gray-700 mr-2">
            Interval:
          </label>
          <select
            value={intervalValue}
            onChange={(e) => setIntervalValue(e.target.value)}
            className="input rounded-lg border border-primary-200 focus:ring-2 focus:ring-primary-400 focus:border-primary-400 shadow-sm px-3 py-2 bg-white text-gray-900 transition-all duration-150 hover:border-primary-400"
          >
            <option value="1m">1 minute</option>
            <option value="5m">5 minutes</option>
            <option value="15m">15 minutes</option>
            <option value="1h">1 hour</option>
          </select>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {getServiceMetricsCards().map((metric, index) => (
          <MetricCard
            key={index}
            title={metric.title}
            value={metric.value}
            subtitle={metric.subtitle}
            icon={metric.icon}
            color={metric.color}
            loading={
              loading || summaryLoading || registeredServices.length === 0
            }
          />
        ))}
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* HTTP Requests Over Time */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">HTTP Requests Over Time</h2>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={formattedRequestsSeries}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="value"
                stroke={colors.primary}
                fill={colors.primary}
                fillOpacity={0.3}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Response Time Over Time */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Response Time Over Time</h2>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={formattedResponseTimeSeries}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip
                formatter={(value) => [
                  `${value}${selectedService === "all" ? "s" : "ms"}`,
                  "Response Time",
                ]}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke={colors.warning}
                strokeWidth={2}
                dot={{ fill: colors.warning, strokeWidth: 2, r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Error Rate/Errors Over Time */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              {selectedService === "all"
                ? "Error Rate Over Time"
                : "Errors Over Time"}
            </h2>
            <div className="flex gap-2 mt-2">
              <span className="text-xs text-gray-500">
                Window: {windowValue}
              </span>
              <span className="text-xs text-gray-500">
                Interval: {intervalValue}
              </span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={formattedErrorsSeries}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip
                formatter={(value) => [
                  `${value}${selectedService === "all" ? "%" : ""}`,
                  selectedService === "all" ? "Error Rate" : "Errors",
                ]}
              />
              <Bar dataKey="value" fill={colors.danger} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Pie Chart Section */}
        {selectedService === "all" ? (
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Response Code Distribution</h2>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={responseCodeData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) =>
                    `${name} ${(percent * 100).toFixed(0)}%`
                  }
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {responseCodeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Request Summary</h2>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={requestSummaryData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) =>
                    `${name} ${(percent * 100).toFixed(0)}%`
                  }
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {requestSummaryData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
};

export default Metrics;
