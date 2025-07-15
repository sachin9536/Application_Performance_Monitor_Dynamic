import React, { useState, useEffect } from "react";
import {
  ServerIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  CpuChipIcon,
  ChartBarIcon,
  ArrowPathIcon,
  TrashIcon,
  EyeIcon,
} from "@heroicons/react/24/outline";
import { apiService, dataUtils } from "../services/api";
import StatusBadge, { StatusPulse } from "../components/StatusBadge";
import MetricCard from "../components/MetricCard";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";

const Services = () => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  // Registered services state
  const [registeredServices, setRegisteredServices] = useState([]);
  const [regName, setRegName] = useState("");
  const [regUrl, setRegUrl] = useState("");
  const [regLoading, setRegLoading] = useState(false);
  const [expandedDetails, setExpandedDetails] = useState({});
  const navigate = useNavigate();

  // Fetch core service data from /api/services
  const fetchServiceData = async () => {
    try {
      setLoading(true);
      const res = await apiService.getServices();
      setServices(res.services || []);
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Failed to fetch service data:", error);
      toast.error("Failed to load service data");
    } finally {
      setLoading(false);
    }
  };

  // Fetch registered services from /api/registered_services
  const fetchRegisteredServices = async () => {
    try {
      const res = await apiService.getRegisteredServices();
      setRegisteredServices(res.registered_services || []);
    } catch (error) {
      console.error("Failed to fetch registered services:", error);
      toast.error("Failed to load registered services");
    }
  };

  useEffect(() => {
    fetchServiceData();
    fetchRegisteredServices();
    const interval = setInterval(() => {
      fetchServiceData();
      fetchRegisteredServices();
    }, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  // Manual refresh
  const handleRefresh = () => {
    fetchServiceData();
    fetchRegisteredServices();
    toast.success("Service data refreshed");
  };

  // Handle registration
  const handleRegister = async (e) => {
    e.preventDefault();
    if (!regName.trim() || !regUrl.trim()) {
      toast.error("Please provide both name and URL");
      return;
    }
    setRegLoading(true);
    try {
      await apiService.registerRegisteredService({
        name: regName.trim(),
        url: regUrl.trim(),
      });
      toast.success("Service registered!");
      setRegName("");
      setRegUrl("");
      fetchRegisteredServices();
    } catch (err) {
      // Error toast handled by API layer
    } finally {
      setRegLoading(false);
    }
  };

  // Add handler for Test Connection
  const handleTestConnection = async () => {
    if (!regUrl.trim()) {
      toast.error("Please enter a URL to test");
      return;
    }
    try {
      const res = await apiService.testMetricsEndpoint(regUrl.trim());
      if (res.success) {
        toast.success(res.message);
      } else {
        toast.error(res.message);
      }
    } catch (e) {
      toast.error("Failed to test connection");
    }
  };

  // Handler to delete a registered service
  const handleDeleteRegisteredService = async (name) => {
    if (!window.confirm(`Are you sure you want to delete service '${name}'?`))
      return;
    try {
      await apiService.deleteRegisteredService(name);
      toast.success(`Service '${name}' deleted`);
      fetchRegisteredServices();
    } catch (err) {
      toast.error(`Failed to delete service '${name}'`);
    }
  };

  const noCoreServices = services.length === 0;
  const noRegisteredServices = registeredServices.length === 0;
  const isEmpty = noCoreServices && noRegisteredServices;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* No Data Yet State */}
      {isEmpty && (
        <div className="flex flex-col items-center justify-center h-96 text-center bg-white rounded-xl shadow-md border border-gray-100 p-12 animate-fadeIn">
          <ServerIcon className="w-16 h-16 text-primary-300 mb-4" />
          <h2 className="text-2xl font-bold mb-2 text-gray-900">
            No Services Registered
          </h2>
          <p className="text-gray-600 mb-4 max-w-xl mx-auto">
            You haven't registered any services yet. Use the{" "}
            <span className="font-semibold">"Register New Application"</span>{" "}
            form below to add your first service. Once registered, you'll see
            live health and performance metrics here.
          </p>
        </div>
      )}
      {/* Header */}
      <div className="flex items-center justify-between bg-white/80 backdrop-blur-xs rounded-xl shadow-sm px-6 py-4 mb-4 border border-gray-100">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-1">
            Application Health
          </h1>
          <p className="text-lg text-gray-600">
            Monitor individual service status and performance
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-base text-gray-500">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="btn btn-primary shadow-md hover:scale-105 transition-transform"
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Register New Application */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-4 mt-4">
        <h2 className="text-xl font-bold mb-2 flex items-center">
          <span className="mr-2 text-primary-600 text-2xl">+</span> Register New
          Application
        </h2>
        <p className="text-gray-600 mb-4">
          Add applications to monitor their performance and health metrics
        </p>
        <form
          className="flex flex-col md:flex-row gap-4 items-center"
          onSubmit={handleRegister}
        >
          <input
            type="text"
            className="input flex-1"
            placeholder="Application Name"
            value={regName}
            onChange={(e) => setRegName(e.target.value)}
            disabled={regLoading}
            required
          />
          <input
            type="url"
            className="input flex-1"
            placeholder="https://your-app.com or http://localhost:3001"
            value={regUrl}
            onChange={(e) => setRegUrl(e.target.value)}
            disabled={regLoading}
            required
          />
          <button
            type="button"
            className="btn btn-secondary min-w-[150px]"
            disabled={!regUrl || regLoading}
            onClick={handleTestConnection}
          >
            Test Connection
          </button>
          <button
            type="submit"
            className="btn btn-primary min-w-[150px]"
            disabled={regLoading}
          >
            {regLoading ? "Registering..." : "Add Application"}
          </button>
        </form>
      </div>

      {/* Only show registered services grid and registration form */}
      <div>
        <h2 className="text-xl font-bold mb-2 mt-8">Registered Applications</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-8">
          {registeredServices.length === 0 && (
            <div className="col-span-full text-center text-gray-500 py-12">
              No registered services yet.
            </div>
          )}
          {registeredServices.map((service) => {
            const isDown =
              service.status !== "healthy" && service.status !== "warning";
            const showDetails = !!expandedDetails[service.name];
            const toggleDetails = () =>
              setExpandedDetails((prev) => ({
                ...prev,
                [service.name]: !prev[service.name],
              }));
            // Color theme
            const cardColor = isDown
              ? "border-red-300 bg-red-50/60"
              : "border-green-200 bg-green-50/60";
            const statusLabel = isDown ? "DOWN" : "UP";
            const statusColor = isDown
              ? "bg-danger-100 text-danger-700"
              : "bg-success-100 text-success-700";
            const statusIcon = isDown ? (
              <ExclamationTriangleIcon className="w-4 h-4 mr-1 text-danger-500" />
            ) : (
              <ServerIcon className="w-4 h-4 mr-1 text-success-500" />
            );
            // Endpoint display
            const endpoint = service.url || "N/A";
            // Copy to clipboard
            const handleCopy = () => {
              navigator.clipboard.writeText(endpoint);
              toast.success("Endpoint copied!");
            };
            // Metrics helpers
            const getMetric = (val, suffix = "", decimals = 2) =>
              val !== undefined && val !== null ? (
                `${Number(val).toFixed(decimals)}${suffix}`
              ) : (
                <span
                  title="Data unavailable while service is offline."
                  className="text-gray-400"
                >
                  N/A
                </span>
              );
            return (
              <div
                key={service.name}
                className={`card shadow-lg hover:shadow-xl transition-all duration-300 rounded-2xl border ${cardColor} mb-6 relative group flex flex-col justify-between min-h-[400px] animate-fadeIn`}
                tabIndex={0}
                aria-label={`Service card for ${service.name}`}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <span className="font-extrabold text-2xl text-gray-900 dark:text-gray-100 tracking-tight">
                      {service.name}
                    </span>
                    <span
                      className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase ml-2 ${statusColor}`}
                    >
                      {statusIcon}
                      {statusLabel}
                    </span>
                  </div>
                </div>
                {/* Endpoint */}
                <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg px-3 py-2 mb-4 text-xs font-mono text-gray-700 dark:text-gray-200">
                  <span className="truncate flex-1" title={endpoint}>
                    {endpoint}
                  </span>
                  <button
                    onClick={handleCopy}
                    className="ml-2 text-gray-400 hover:text-primary-600 focus:outline-none transition-colors"
                    title="Copy endpoint"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-4 w-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 16h8a2 2 0 002-2V8m-2-2H8a2 2 0 00-2 2v8a2 2 0 002 2zm2-10v4m0 0l-2-2m2 2l2-2"
                      />
                    </svg>
                  </button>
                </div>
                {/* Error/Healthy Banner */}
                {isDown ? (
                  <div className="flex items-center bg-red-100/80 text-red-800 rounded-lg px-4 py-3 mb-4 text-sm">
                    <ExclamationTriangleIcon className="w-5 h-5 mr-2 text-red-400" />
                    <span className="font-semibold mr-2">
                      Service is unreachable or offline.
                    </span>
                    <button
                      className="ml-auto underline text-xs text-red-700 hover:text-red-900 focus:outline-none"
                      onClick={toggleDetails}
                      tabIndex={0}
                    >
                      {showDetails ? "Hide details" : "Show details"}
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center bg-green-100/80 text-green-800 rounded-lg px-4 py-3 mb-4 text-sm">
                    <ServerIcon className="w-4 h-4 mr-2 text-green-500" />
                    <span className="font-medium">All systems normal</span>
                  </div>
                )}
                {/* Error details (expandable) */}
                {isDown && showDetails && service.error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-xs text-red-700 font-mono whitespace-pre-wrap">
                    {service.error}
                  </div>
                )}
                {/* Metrics Grid - ALL METRICS */}
                <div className="grid grid-cols-2 gap-4 mb-6 mt-2">
                  <MetricCard
                    title="Health Status"
                    value={
                      isDown ? (
                        <span className="text-danger-700 font-semibold">
                          Degraded
                        </span>
                      ) : (
                        <span className="text-success-700 font-semibold">
                          Healthy
                        </span>
                      )
                    }
                    subtitle="System"
                    icon={ServerIcon}
                    color={isDown ? "danger" : "success"}
                    loading={loading}
                  />
                  <MetricCard
                    title="Uptime"
                    value={
                      isDown ? (
                        <span
                          title="Data unavailable while service is offline."
                          className="text-gray-400"
                        >
                          N/A
                        </span>
                      ) : service.uptime !== undefined &&
                        service.uptime !== null ? (
                        getMetric(service.uptime, " min", 0)
                      ) : (
                        <span className="text-gray-400">N/A</span>
                      )
                    }
                    subtitle="Since Last Restart"
                    icon={ClockIcon}
                    color={isDown ? "gray" : "primary"}
                    loading={loading}
                  />
                  <MetricCard
                    title="Latency"
                    value={
                      isDown ? (
                        <span
                          title="Data unavailable while service is offline."
                          className="text-gray-400"
                        >
                          N/A
                        </span>
                      ) : (
                        getMetric(
                          service.metrics?.avg_latency
                            ? service.metrics.avg_latency * 1000
                            : service.metrics?.ttfb_ms,
                          " ms"
                        )
                      )
                    }
                    subtitle="Average Latency Time"
                    icon={ChartBarIcon}
                    color={
                      isDown
                        ? "gray"
                        : (service.metrics?.avg_latency
                            ? service.metrics.avg_latency * 1000
                            : service.metrics?.ttfb_ms) > 500
                        ? "danger"
                        : (service.metrics?.avg_latency
                            ? service.metrics.avg_latency * 1000
                            : service.metrics?.ttfb_ms) > 200
                        ? "warning"
                        : "success"
                    }
                    loading={loading}
                  />
                  <MetricCard
                    title="CPU"
                    value={
                      isDown ? (
                        <span
                          title="Data unavailable while service is offline."
                          className="text-gray-400"
                        >
                          N/A
                        </span>
                      ) : (
                        getMetric(service.metrics?.cpu_percent, "%")
                      )
                    }
                    subtitle="CPU Usage"
                    icon={CpuChipIcon}
                    color={
                      isDown
                        ? "gray"
                        : service.metrics?.cpu_percent > 80
                        ? "danger"
                        : service.metrics?.cpu_percent > 50
                        ? "warning"
                        : "success"
                    }
                    loading={loading}
                  />
                  <MetricCard
                    title="Memory"
                    value={
                      isDown ? (
                        <span
                          title="Data unavailable while service is offline."
                          className="text-gray-400"
                        >
                          N/A
                        </span>
                      ) : (
                        getMetric(service.metrics?.memory_used_mb, " MB")
                      )
                    }
                    subtitle="Memory Usage"
                    icon={CpuChipIcon}
                    color={
                      isDown
                        ? "gray"
                        : service.metrics?.memory_used_mb > 500
                        ? "danger"
                        : service.metrics?.memory_used_mb > 200
                        ? "warning"
                        : "success"
                    }
                    loading={loading}
                  />
                  <MetricCard
                    title="Error Rate"
                    value={
                      isDown ? (
                        <span
                          title="Data unavailable while service is offline."
                          className="text-gray-400"
                        >
                          N/A
                        </span>
                      ) : service.metrics?.errors_total !== undefined &&
                        service.metrics?.http_requests_total !== undefined &&
                        Number(service.metrics.http_requests_total) > 0 ? (
                        `${(
                          (service.metrics.errors_total /
                            service.metrics.http_requests_total) *
                          100
                        ).toFixed(2)}%`
                      ) : (
                        <span className="text-gray-400">N/A</span>
                      )
                    }
                    subtitle="Errors"
                    icon={ExclamationTriangleIcon}
                    color={
                      isDown
                        ? "gray"
                        : service.metrics?.errors_total > 5
                        ? "danger"
                        : service.metrics?.errors_total > 1
                        ? "warning"
                        : "success"
                    }
                    loading={loading}
                  />
                  <MetricCard
                    title="Requests"
                    value={
                      isDown ? (
                        <span
                          title="Data unavailable while service is offline."
                          className="text-gray-400"
                        >
                          N/A
                        </span>
                      ) : (
                        getMetric(service.metrics?.http_requests_total)
                      )
                    }
                    subtitle="Total"
                    icon={ChartBarIcon}
                    color={isDown ? "gray" : "primary"}
                    loading={loading}
                  />
                  <MetricCard
                    title="Errors"
                    value={
                      isDown ? (
                        <span
                          title="Data unavailable while service is offline."
                          className="text-gray-400"
                        >
                          N/A
                        </span>
                      ) : (
                        getMetric(service.metrics?.errors_total)
                      )
                    }
                    subtitle="Total"
                    icon={ExclamationTriangleIcon}
                    color={
                      isDown
                        ? "gray"
                        : service.metrics?.errors_total > 0
                        ? "danger"
                        : "success"
                    }
                    loading={loading}
                  />
                </div>
                {/* Action Buttons - More Prominent */}
                <div className="flex items-center justify-between mt-auto pt-6 border-t border-gray-100">
                  <div className="flex items-center text-xs text-gray-500">
                    <ClockIcon className="w-4 h-4 mr-1" />
                    Last updated:{" "}
                    {service.last_scraped
                      ? dataUtils.formatTimestamp(service.last_scraped * 1000)
                      : "N/A"}
                  </div>
                  <div className="flex items-center gap-3">
                    {/* Delete button - Always visible but subtle */}
                    <button
                      className="text-red-500 hover:text-red-700 hover:bg-red-50 p-2 rounded-lg transition-all duration-200 group"
                      onClick={() =>
                        handleDeleteRegisteredService(service.name)
                      }
                      title="Delete service"
                    >
                      <TrashIcon className="w-4 h-4 group-hover:scale-110 transition-transform" />
                    </button>
                    {/* View Details Button - More prominent */}
                    {service.name && (
                      <button
                        className="btn btn-primary flex items-center gap-2 px-6 py-2.5 text-sm font-semibold shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200"
                        onClick={() => navigate(`/services/${service.name}`)}
                        title="View Details"
                      >
                        <EyeIcon className="w-4 h-4" />
                        <span>View Details</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default Services;
