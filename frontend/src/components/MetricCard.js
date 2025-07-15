import React from "react";
import { clsx } from "clsx";
import {
  ChartBarIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
} from "@heroicons/react/24/outline";
import StatusBadge from "./StatusBadge";

const MetricCard = ({
  title,
  value,
  subtitle,
  trend,
  trendValue,
  color = "primary",
  icon: Icon,
  loading = false,
  onClick,
}) => {
  const colorClasses = {
    primary: "bg-primary-50 text-primary-700 border-primary-200",
    success: "bg-success-50 text-success-700 border-success-200",
    warning: "bg-warning-50 text-warning-700 border-warning-200",
    danger: "bg-danger-50 text-danger-700 border-danger-200",
    gray: "bg-gray-50 text-gray-700 border-gray-200",
  };

  const iconColorClasses = {
    primary: "text-blue-600",
    success: "text-green-600",
    warning: "text-yellow-600",
    danger: "text-red-600",
    gray: "text-gray-600",
  };

  const getTrendIcon = () => {
    if (trend === "up") {
      return <ArrowTrendingUpIcon className="w-4 h-4 text-green-500" />;
    } else if (trend === "down") {
      return <ArrowTrendingDownIcon className="w-4 h-4 text-red-500" />;
    }
    return null;
  };

  const getTrendColor = (trend) => {
    if (trend === "up") return "text-success-600";
    if (trend === "down") return "text-danger-600";
    return "text-gray-500";
  };

  return (
    <div
      className={clsx(
        "metric-card transition-all duration-200 hover:shadow-md hover:scale-105 animate-fadeIn",
        onClick && "cursor-pointer"
      )}
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <p className="metric-label">{title}</p>
            {Icon && (
              <div
                className={clsx("p-2 rounded-lg border", colorClasses[color])}
              >
                <Icon className={`w-4 h-4 ${iconColorClasses[color]}`} />
              </div>
            )}
          </div>

          <div className="mt-2">
            {loading ? (
              <div className="animate-pulse">
                <div className="h-8 bg-gray-200 rounded w-20"></div>
              </div>
            ) : (
              <div className="flex items-center space-x-2 mb-1">
                <p className="text-2xl font-bold text-gray-900">{value}</p>
                {getTrendIcon()}
              </div>
            )}
          </div>

          {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
        </div>
      </div>

      {/* Trend indicator */}
      {trend && (
        <div className="mt-3 flex items-center">
          <span
            className={clsx("ml-1 text-sm font-medium", getTrendColor(trend))}
          >
            {trendValue}
          </span>
          <span className="ml-1 text-xs text-gray-500">vs last period</span>
        </div>
      )}
    </div>
  );
};

export default MetricCard;
