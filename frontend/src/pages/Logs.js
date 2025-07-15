import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  ArrowPathIcon,
  EyeIcon,
  DocumentTextIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import { apiService, dataUtils } from "../services/api";
import StatusBadge from "../components/StatusBadge";
import toast from "react-hot-toast";
import { useLocation } from "react-router-dom";

const LOG_LEVELS = [
  { label: "All", value: "ALL" },
  { label: "Error", value: "ERROR" },
  { label: "Warning", value: "WARNING" },
  { label: "Info", value: "INFO" },
  { label: "Debug", value: "DEBUG" },
];

const levelIcon = {
  ERROR: <ExclamationTriangleIcon className="w-5 h-5 text-danger-600 mr-2" />,
  WARNING: (
    <ExclamationTriangleIcon className="w-5 h-5 text-warning-600 mr-2" />
  ),
  INFO: <InformationCircleIcon className="w-5 h-5 text-primary-600 mr-2" />,
  DEBUG: <DocumentTextIcon className="w-5 h-5 text-gray-500 mr-2" />,
};

const Logs = () => {
  const location = useLocation();
  const [logs, setLogs] = useState([]);
  const [filteredLogs, setFilteredLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedLog, setSelectedLog] = useState(null);
  const [showModal, setShowModal] = useState(false);

  // Filter states
  const [filters, setFilters] = useState({
    level: "all",
    service: "all",
    search: "",
    timeRange: "1h",
  });

  const [showFilters, setShowFilters] = useState(false);
  const [hasMoreLogs, setHasMoreLogs] = useState(true);
  const logsEndRef = useRef(null);

  // Handle URL parameters for service filtering
  useEffect(() => {
    const urlParams = new URLSearchParams(location.search);
    const serviceParam = urlParams.get("service");
    if (serviceParam) {
      setFilters((prev) => ({
        ...prev,
        service: serviceParam,
      }));
    }
  }, [location.search]);

  // Fetch logs data
  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const logsData = await apiService.getLogs(1000); // Fetch 1,000 logs by default
      setLogs(logsData.logs || []);
      setHasMoreLogs(logsData.total > logsData.logs.length);
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Failed to fetch logs:", error);
      toast.error("Failed to load logs");
    } finally {
      setLoading(false);
    }
  }, []);

  // Load more logs
  const loadMoreLogs = async () => {
    try {
      setLoading(true);
      const currentCount = logs.length;
      const logsData = await apiService.getLogs(1000, currentCount); // Fetch 1,000 more logs
      setLogs((prevLogs) => [...prevLogs, ...(logsData.logs || [])]);
      setHasMoreLogs(logsData.total > currentCount + logsData.logs.length);
      toast.success(`Loaded ${logsData.logs.length} more logs`);
    } catch (error) {
      console.error("Failed to load more logs:", error);
      toast.error("Failed to load more logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();

    let interval;
    if (autoRefresh) {
      interval = setInterval(fetchLogs, 10000); // Refresh every 10 seconds
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh, fetchLogs]);

  // Apply filters
  useEffect(() => {
    let filtered = [...logs];

    // Level filter
    if (filters.level !== "all") {
      filtered = filtered.filter(
        (log) => log.level?.toLowerCase() === filters.level.toLowerCase()
      );
    }

    // Service filter
    if (filters.service !== "all") {
      filtered = filtered.filter(
        (log) => log.service?.toLowerCase() === filters.service.toLowerCase()
      );
    }

    // Search filter
    if (filters.search) {
      const searchTerm = filters.search.toLowerCase();
      filtered = filtered.filter(
        (log) =>
          log.message?.toLowerCase().includes(searchTerm) ||
          log.service?.toLowerCase().includes(searchTerm) ||
          log.level?.toLowerCase().includes(searchTerm)
      );
    }

    // Time range filter
    if (filters.timeRange !== "all") {
      // Always use UTC for now and log times
      const nowUtc = Date.now();
      let cutoffTimeUtc;

      switch (filters.timeRange) {
        case "15m":
          cutoffTimeUtc = nowUtc - 15 * 60 * 1000;
          break;
        case "1h":
          cutoffTimeUtc = nowUtc - 60 * 60 * 1000;
          break;
        case "6h":
          cutoffTimeUtc = nowUtc - 6 * 60 * 60 * 1000;
          break;
        case "24h":
          cutoffTimeUtc = nowUtc - 24 * 60 * 60 * 1000;
          break;
        default:
          cutoffTimeUtc = 0;
      }

      filtered = filtered.filter((log) => {
        // Parse log.timestamp as UTC
        const logTimeUtc = Date.parse(log.timestamp);
        return logTimeUtc >= cutoffTimeUtc;
      });
    }

    setFilteredLogs(filtered);
  }, [logs, filters]);

  // Sort filtered logs by timestamp descending (newest first)
  const sortedFilteredLogs = filteredLogs
    .slice()
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  // Scroll to bottom for new logs
  useEffect(() => {
    if (autoRefresh && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [filteredLogs]);

  // Get unique services and levels for filters
  const services = [
    "all",
    ...new Set(logs.map((log) => log.service).filter(Boolean)),
  ];
  const levels = ["all", "error", "warning", "info", "debug"];

  // Get log level color
  const getLogLevelColor = (level) => {
    switch (level?.toLowerCase()) {
      case "error":
        return "text-red-600 bg-red-50 border-red-200";
      case "warning":
        return "text-yellow-600 bg-yellow-50 border-yellow-200";
      case "info":
        return "text-blue-600 bg-blue-50 border-blue-200";
      case "debug":
        return "text-gray-600 bg-gray-50 border-gray-200";
      default:
        return "text-gray-600 bg-gray-50 border-gray-200";
    }
  };

  // Get log level icon
  const getLogLevelIcon = (level) => {
    switch (level?.toLowerCase()) {
      case "error":
        return <ExclamationTriangleIcon className="w-4 h-4" />;
      case "warning":
        return <ExclamationTriangleIcon className="w-4 h-4" />;
      case "info":
        return <InformationCircleIcon className="w-4 h-4" />;
      case "debug":
        return <DocumentTextIcon className="w-4 h-4" />;
      default:
        return <DocumentTextIcon className="w-4 h-4" />;
    }
  };

  // Open log details modal
  const openLogDetails = (log) => {
    setSelectedLog(log);
    setShowModal(true);
  };

  // Clear all filters
  const clearFilters = () => {
    setFilters({
      level: "all",
      service: "all",
      search: "",
      timeRange: "1h",
    });
  };

  // Export logs
  const exportLogs = () => {
    const csvContent = [
      "Timestamp,Level,Service,Message",
      ...filteredLogs.map(
        (log) =>
          `"${log.timestamp}","${log.level}","${
            log.service
          }","${log.message?.replace(/"/g, '""')}"`
      ),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `logs-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    toast.success("Logs exported successfully");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">System Logs</h1>
          <p className="text-gray-600">Real-time log monitoring and analysis</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-sm text-gray-500">
            {filteredLogs.length} of {logs.length} logs
            {hasMoreLogs && (
              <span className="text-blue-600"> (more available)</span>
            )}
          </div>
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="btn btn-primary"
          >
            <ArrowPathIcon
              className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`}
            />
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Search */}
        <div className="flex-1 relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search logs..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Filter Toggle */}
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="btn btn-secondary"
        >
          <FunnelIcon className="w-4 h-4 mr-2" />
          Filters
        </button>

        {/* Auto Refresh Toggle */}
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          className={`btn ${autoRefresh ? "btn-success" : "btn-secondary"}`}
        >
          <ClockIcon className="w-4 h-4 mr-2" />
          {autoRefresh ? "Auto On" : "Auto Off"}
        </button>

        {/* Export */}
        <button
          onClick={exportLogs}
          disabled={filteredLogs.length === 0}
          className="btn btn-secondary"
        >
          <DocumentTextIcon className="w-4 h-4 mr-2" />
          Export
        </button>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Filters</h3>
            <button
              onClick={clearFilters}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Clear All
            </button>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Level Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Log Level
                </label>
                <select
                  value={filters.level}
                  onChange={(e) =>
                    setFilters({ ...filters, level: e.target.value })
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {levels.map((level) => (
                    <option key={level} value={level}>
                      {level === "all" ? "All Levels" : level.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>

              {/* Service Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Service
                </label>
                <select
                  value={filters.service}
                  onChange={(e) =>
                    setFilters({ ...filters, service: e.target.value })
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {services.map((service) => (
                    <option key={service} value={service}>
                      {service === "all" ? "All Services" : service}
                    </option>
                  ))}
                </select>
              </div>

              {/* Time Range Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Time Range
                </label>
                <select
                  value={filters.timeRange}
                  onChange={(e) =>
                    setFilters({ ...filters, timeRange: e.target.value })
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="15m">Last 15 minutes</option>
                  <option value="1h">Last hour</option>
                  <option value="6h">Last 6 hours</option>
                  <option value="24h">Last 24 hours</option>
                  <option value="all">All time</option>
                </select>
              </div>

              {/* Active Filters Summary */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Active Filters
                </label>
                <div className="text-sm text-gray-600">
                  {filters.level !== "all" && (
                    <div className="flex items-center space-x-2">
                      <span>Level: {filters.level}</span>
                      <button
                        onClick={() => setFilters({ ...filters, level: "all" })}
                        className="text-red-500 hover:text-red-700"
                      >
                        <XMarkIcon className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                  {filters.service !== "all" && (
                    <div className="flex items-center space-x-2">
                      <span>Service: {filters.service}</span>
                      <button
                        onClick={() =>
                          setFilters({ ...filters, service: "all" })
                        }
                        className="text-red-500 hover:text-red-700"
                      >
                        <XMarkIcon className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                  {filters.search && (
                    <div className="flex items-center space-x-2">
                      <span>Search: "{filters.search}"</span>
                      <button
                        onClick={() => setFilters({ ...filters, search: "" })}
                        className="text-red-500 hover:text-red-700"
                      >
                        <XMarkIcon className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Logs List */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center justify-between">
            <h2 className="card-title">Recent Logs</h2>
            <div className="text-sm text-gray-500">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </div>
          </div>
        </div>

        <div className="max-h-96 overflow-y-auto">
          {filteredLogs.length === 0 ? (
            <div className="text-center py-8">
              <DocumentTextIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">
                {loading
                  ? "Loading logs..."
                  : "No logs found matching your filters"}
              </p>
            </div>
          ) : (
            <>
              <div className="divide-y divide-gray-200">
                {sortedFilteredLogs.map((log, index) => (
                  <div
                    key={index}
                    className="p-4 hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => openLogDetails(log)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-3 mb-2">
                          <div
                            className={`flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium border ${getLogLevelColor(
                              log.level
                            )}`}
                          >
                            {getLogLevelIcon(log.level)}
                            <span>{log.level?.toUpperCase() || "UNKNOWN"}</span>
                          </div>
                          {log.service && (
                            <StatusBadge status="info" text={log.service} />
                          )}
                          <span className="text-sm text-gray-500">
                            {dataUtils.formatTimestamp(log.timestamp)}
                          </span>
                        </div>
                        <p className="text-sm text-gray-900 truncate">
                          {log.message}
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openLogDetails(log);
                        }}
                        className="ml-4 p-1 text-gray-400 hover:text-gray-600"
                      >
                        <EyeIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>

              {/* Load More Button */}
              {hasMoreLogs && !loading && (
                <div className="p-4 text-center border-t border-gray-200">
                  <button
                    onClick={loadMoreLogs}
                    disabled={loading}
                    className="btn btn-primary"
                  >
                    {loading ? "Loading..." : "Load More Logs"}
                  </button>
                  <p className="text-sm text-gray-500 mt-2">
                    Currently showing {logs.length} of{" "}
                    {logs.length + (hasMoreLogs ? " many more" : "")} total logs
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Log Details Modal */}
      {showModal && selectedLog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full mx-4 max-h-96 overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b">
              <h3 className="text-lg font-semibold text-gray-900">
                Log Details
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="w-6 h-6" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium text-gray-700">Timestamp:</span>
                  <div className="text-gray-900">
                    {dataUtils.formatTimestamp(selectedLog.timestamp)}
                  </div>
                </div>
                <div>
                  <span className="font-medium text-gray-700">Level:</span>
                  <div
                    className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${getLogLevelColor(
                      selectedLog.level
                    )}`}
                  >
                    {getLogLevelIcon(selectedLog.level)}
                    <span className="ml-1">
                      {selectedLog.level?.toUpperCase() || "UNKNOWN"}
                    </span>
                  </div>
                </div>
                {selectedLog.service && (
                  <div>
                    <span className="font-medium text-gray-700">Service:</span>
                    <div className="text-gray-900">{selectedLog.service}</div>
                  </div>
                )}
                {selectedLog.status_code && (
                  <div>
                    <span className="font-medium text-gray-700">
                      Status Code:
                    </span>
                    <div className="text-gray-900">
                      {selectedLog.status_code}
                    </div>
                  </div>
                )}
                {selectedLog.latency_ms && (
                  <div>
                    <span className="font-medium text-gray-700">Latency:</span>
                    <div className="text-gray-900">
                      {selectedLog.latency_ms}ms
                    </div>
                  </div>
                )}
              </div>
              <div>
                <span className="font-medium text-gray-700">Message:</span>
                <div className="mt-2 p-3 bg-gray-50 rounded-lg">
                  <pre className="text-sm text-gray-900 whitespace-pre-wrap font-mono">
                    {selectedLog.message}
                  </pre>
                </div>
              </div>
              {selectedLog.raw && (
                <div>
                  <span className="font-medium text-gray-700">Raw Log:</span>
                  <div className="mt-2 p-3 bg-gray-50 rounded-lg">
                    <pre className="text-xs text-gray-600 whitespace-pre-wrap font-mono">
                      {selectedLog.raw}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Logs;
