import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Bars3Icon,
  ArrowPathIcon,
  BellIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
} from "@heroicons/react/24/outline";
import { apiService, dataUtils } from "../services/api";
import toast from "react-hot-toast";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";

const Header = ({ onMenuClick }) => {
  const [systemStatus, setSystemStatus] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [anomalies, setAnomalies] = useState([]);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const bellRef = useRef();
  const { logout } = useAuth();
  const navigate = useNavigate();

  const fetchSystemStatus = useCallback(async () => {
    try {
      const health = await apiService.getHealth();
      setSystemStatus(health);
      setLastUpdated(new Date());
    } catch (error) {
      console.error("System status fetch failed:", error);
    }
  }, []);

  const fetchAnomalies = useCallback(async () => {
    try {
      const res = await fetch("/api/analytics");
      const data = await res.json();
      setAnomalies(data.anomalies || []);
    } catch {
      setAnomalies([]);
    }
  }, []);

  useEffect(() => {
    fetchSystemStatus();
    fetchAnomalies();
    const sysInterval = setInterval(fetchSystemStatus, 30000);
    const anoInterval = setInterval(fetchAnomalies, 30000);
    return () => {
      clearInterval(sysInterval);
      clearInterval(anoInterval);
    };
  }, [fetchSystemStatus, fetchAnomalies]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (popoverOpen && bellRef.current && !bellRef.current.contains(e.target)) {
        setPopoverOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [popoverOpen]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([fetchSystemStatus(), fetchAnomalies()]);
      toast.success("Data refreshed");
    } catch {
      toast.error("Failed to refresh data");
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/welcome");
  };

  const getStatusClasses = (status) => {
    const base = "flex items-center px-2 py-1 rounded text-xs font-medium";
    return status === "healthy"
      ? `${base} text-success-700 bg-success-50 border border-success-200`
      : `${base} text-gray-700 bg-gray-50 border border-gray-200`;
  };

  const bellColor = anomalies.length
    ? "text-warning-500 hover:text-warning-600 dark:text-warning-400 dark:hover:text-warning-300"
    : "text-gray-400 hover:text-gray-600 dark:text-gray-300 dark:hover:text-white";

  return (
    <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
        {/* Left Section */}
        <div className="flex items-center">
          <button
            className="text-gray-400 hover:text-gray-600 dark:text-gray-300 dark:hover:text-white lg:hidden"
            onClick={onMenuClick}
            aria-label="Open menu"
          >
            <Bars3Icon className="w-6 h-6" />
          </button>
          <h1 className="ml-4 text-xl font-semibold text-gray-900 dark:text-gray-100">
            AppVital
          </h1>
        </div>

        {/* Right Section */}
        <div className="flex items-center space-x-4">
          {/* Component Status Badges */}
          {systemStatus?.components && (
            <div className="hidden md:flex items-center space-x-2">
              {Object.entries(systemStatus.components).map(([name, status]) => (
                <div key={name} className={getStatusClasses(status)} title={`${name}: ${status}`}>
                  <div
                    className={`w-1.5 h-1.5 rounded-full mr-1 ${
                      status === "healthy" ? "bg-success-500" : "bg-gray-400"
                    }`}
                  />
                  {name}
                </div>
              ))}
            </div>
          )}

          {/* Metrics Summary */}
          {systemStatus?.metrics && (
            <div className="hidden lg:flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-300">
              <span>Logs: {dataUtils.formatNumber(systemStatus.metrics.total_logs)}</span>
              <span>Errors: {dataUtils.formatNumber(systemStatus.metrics.total_errors)}</span>
              <span>Anomalies: {dataUtils.formatNumber(systemStatus.metrics.active_anomalies)}</span>
            </div>
          )}

          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-2 text-gray-400 hover:text-gray-600 dark:text-gray-300 dark:hover:text-white"
            title="Refresh"
          >
            <ArrowPathIcon className={`w-5 h-5 ${isRefreshing ? "animate-spin" : ""}`} />
          </button>

          {/* Notifications */}
          <div className="relative" ref={bellRef}>
            <button
              className={`p-2 ${bellColor}`}
              title={
                anomalies.length
                  ? `${anomalies.length} anomaly${anomalies.length > 1 ? "ies" : "y"}`
                  : "Notifications"
              }
              onClick={() => setPopoverOpen(!popoverOpen)}
              aria-label="Anomalies"
            >
              <BellIcon className="w-5 h-5" />
              {anomalies.length > 0 && (
                <span className="absolute -top-1 -right-1 bg-warning-500 text-white text-xs rounded-full px-1.5 py-0.5 font-bold shadow-lg border-2 border-white dark:border-gray-800">
                  {anomalies.length}
                </span>
              )}
            </button>

            {popoverOpen && (
              <div className="absolute right-0 mt-2 w-80 max-w-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50 animate-fadeIn">
                <div className="p-4">
                  <div className="flex items-center mb-2">
                    <ExclamationTriangleIcon className="w-5 h-5 text-warning-500 mr-2" />
                    <span className="font-semibold text-gray-900 dark:text-gray-100">
                      {anomalies.length > 0 ? "Active Anomalies" : "No Active Anomalies"}
                    </span>
                  </div>
                  {anomalies.length > 0 ? (
                    <ul className="space-y-2">
                      {anomalies.map((msg, idx) => (
                        <li
                          key={idx}
                          className="flex items-start bg-warning-50 dark:bg-warning-900 border-l-4 border-warning-500 rounded p-2 text-warning-900 dark:text-warning-100"
                        >
                          <ExclamationTriangleIcon className="w-4 h-4 mt-0.5 mr-2 text-warning-500 dark:text-warning-300" />
                          <span>{msg}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-center text-gray-500 dark:text-gray-400 py-4">
                      No active anomalies.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Logout */}
          <button
            onClick={handleLogout}
            className="btn btn-secondary px-3 py-2 text-sm font-medium rounded-lg shadow-sm border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            Logout
          </button>

          {/* Last Updated Time */}
          <div className="hidden sm:flex items-center text-xs text-gray-500 dark:text-gray-300">
            <span>Updated: {lastUpdated.toLocaleTimeString()}</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;