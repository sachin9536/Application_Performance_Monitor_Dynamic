import React, { useState, useEffect, useRef } from "react";
import {
  Bars3Icon,
  ArrowPathIcon,
  BellIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
} from "@heroicons/react/24/outline";
import { apiService, dataUtils } from "../services/api";
import toast from "react-hot-toast";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";

const Header = ({ onMenuClick }) => {
  const [systemStatus, setSystemStatus] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  // Anomaly notification state
  const [anomalies, setAnomalies] = useState([]);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const bellRef = useRef();

  const { logout } = useAuth();
  const navigate = useNavigate();

  // Fetch system status
  const fetchSystemStatus = async () => {
    try {
      const health = await apiService.getHealth();
      setSystemStatus(health);
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Failed to fetch system status:", error);
    }
  };

  // Fetch anomalies
  const fetchAnomalies = async () => {
    try {
      const res = await fetch("/api/analytics");
      const data = await res.json();
      setAnomalies(data.anomalies || []);
    } catch (e) {
      setAnomalies([]);
    }
  };

  // Auto-refresh every 30 seconds
  useEffect(() => {
    fetchSystemStatus();
    const interval = setInterval(fetchSystemStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    fetchAnomalies();
    const interval = setInterval(fetchAnomalies, 30000);
    return () => clearInterval(interval);
  }, []);

  // Manual refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await fetchSystemStatus();
      await fetchAnomalies();
      toast.success("Data refreshed successfully");
    } catch (error) {
      toast.error("Failed to refresh data");
    } finally {
      setIsRefreshing(false);
    }
  };

  // Popover close on outside click
  useEffect(() => {
    if (!popoverOpen) return;
    function handleClick(e) {
      if (bellRef.current && !bellRef.current.contains(e.target)) {
        setPopoverOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [popoverOpen]);

  // Get status icon and color
  const getStatusIcon = (status) => {
    switch (status) {
      case "healthy":
        return <CheckCircleIcon className="w-5 h-5 text-success-600" />;
      default:
        return <ExclamationTriangleIcon className="w-5 h-5 text-gray-600" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case "healthy":
        return "text-success-700 bg-success-50 border-success-200";
      default:
        return "text-gray-700 bg-gray-50 border-gray-200";
    }
  };

  // Bell color logic
  const bellColor =
    anomalies.length > 0
      ? "text-warning-500 hover:text-warning-600 dark:text-warning-400 dark:hover:text-warning-300"
      : "text-gray-400 hover:text-gray-600 dark:text-gray-300 dark:hover:text-white";

  const handleLogout = () => {
    logout();
    navigate("/welcome");
  };

  return (
    <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
        {/* Left side */}
        <div className="flex items-center">
          <button
            type="button"
            className="text-gray-400 hover:text-gray-600 dark:text-gray-300 dark:hover:text-white lg:hidden"
            onClick={onMenuClick}
          >
            <Bars3Icon className="w-6 h-6" />
          </button>

          <div className="ml-4 lg:ml-0">
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
              AppVital
            </h1>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center space-x-4">
          {/* System Status */}
          {/* Removed the system status button/badge that shows 'Unhealthy' in the header */}

          {/* Component Status */}
          {systemStatus?.components && (
            <div className="hidden md:flex items-center space-x-2">
              {Object.entries(systemStatus.components).map(
                ([component, status]) => (
                  <div
                    key={component}
                    className={`flex items-center px-2 py-1 rounded text-xs font-medium ${getStatusColor(
                      status
                    )} dark:bg-gray-700 dark:border-gray-600`}
                    title={`${component}: ${status}`}
                  >
                    <div
                      className={`w-1.5 h-1.5 rounded-full mr-1 ${
                        status === "healthy"
                          ? "bg-success-500"
                          : "bg-gray-400"
                      }`}
                    />
                    {component}
                  </div>
                )
              )}
            </div>
          )}

          {/* Metrics Summary */}
          {systemStatus?.metrics && (
            <div className="hidden lg:flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-300">
              <div className="flex items-center">
                <span className="font-medium">Logs:</span>
                <span className="ml-1">
                  {dataUtils.formatNumber(systemStatus.metrics.total_logs)}
                </span>
              </div>
              <div className="flex items-center">
                <span className="font-medium">Errors:</span>
                <span className="ml-1">
                  {dataUtils.formatNumber(systemStatus.metrics.total_errors)}
                </span>
              </div>
              <div className="flex items-center">
                <span className="font-medium">Anomalies:</span>
                <span className="ml-1">
                  {dataUtils.formatNumber(
                    systemStatus.metrics.active_anomalies
                  )}
                </span>
              </div>
            </div>
          )}

          {/* Refresh Button */}
          <button
            type="button"
            className="p-2 text-gray-400 hover:text-gray-600 dark:text-gray-300 dark:hover:text-white transition-colors duration-200"
            onClick={handleRefresh}
            disabled={isRefreshing}
            title="Refresh data"
          >
            <ArrowPathIcon
              className={`w-5 h-5 ${isRefreshing ? "animate-spin" : ""}`}
            />
          </button>

          {/* Notifications Bell */}
          <div className="relative" ref={bellRef}>
            <button
              type="button"
              className={`p-2 transition-colors duration-200 relative ${bellColor}`}
              title={
                anomalies.length > 0
                  ? `${anomalies.length} anomaly${
                      anomalies.length > 1 ? "ies" : "y"
                    } detected`
                  : "Notifications"
              }
              onClick={() => setPopoverOpen((v) => !v)}
              aria-label="Show anomalies"
            >
              <BellIcon className="w-5 h-5" />
              {anomalies.length > 0 && (
                <span className="absolute -top-1 -right-1 bg-warning-500 text-white text-xs rounded-full px-1.5 py-0.5 font-bold shadow-lg border-2 border-white dark:border-gray-800">
                  {anomalies.length}
                </span>
              )}
            </button>
            {/* Popover */}
            {popoverOpen && (
              <div className="absolute right-0 mt-2 w-80 max-w-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50 animate-fadeIn">
                <div className="p-4">
                  <div className="flex items-center mb-2">
                    <ExclamationTriangleIcon className="w-5 h-5 text-warning-500 mr-2" />
                    <span className="font-semibold text-gray-900 dark:text-gray-100">
                      {anomalies.length > 0
                        ? "Active Anomalies"
                        : "No Active Anomalies"}
                    </span>
                  </div>
                  {anomalies.length > 0 ? (
                    <ul className="space-y-2">
                      {anomalies.map((anomaly, idx) => (
                        <li
                          key={idx}
                          className="flex items-start bg-warning-50 dark:bg-warning-900 border-l-4 border-warning-500 rounded p-2 text-warning-900 dark:text-warning-100"
                        >
                          <ExclamationTriangleIcon className="w-4 h-4 mt-0.5 mr-2 text-warning-500 dark:text-warning-300" />
                          <span>{anomaly}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-gray-500 dark:text-gray-400 py-4 text-center">
                      No active anomalies.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Logout Button */}
          <button
            type="button"
            className="btn btn-secondary px-3 py-2 text-sm font-medium rounded-lg shadow-sm border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            onClick={handleLogout}
          >
            Logout
          </button>

          {/* Last Updated */}
          <div className="hidden sm:flex items-center text-xs text-gray-500 dark:text-gray-300">
            <span>Updated: {lastUpdated.toLocaleTimeString()}</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
