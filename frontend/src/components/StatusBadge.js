import React from "react";
import { clsx } from "clsx";
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/solid";

const StatusBadge = ({
  status,
  size = "md",
  showIcon = true,
  showText = true,
  className = "",
}) => {
  const statusConfig = {
    healthy: {
      label: "Healthy",
      color: "success",
      icon: CheckCircleIcon,
      bgColor: "bg-success-100",
      textColor: "text-success-800",
      borderColor: "border-success-200",
      iconColor: "text-success-600",
    },
    unhealthy: {
      label: "Unhealthy",
      color: "danger",
      icon: XCircleIcon,
      bgColor: "bg-danger-100",
      textColor: "text-danger-800",
      borderColor: "border-danger-200",
      iconColor: "text-danger-600",
    },
    warning: {
      label: "Warning",
      color: "warning",
      icon: ExclamationTriangleIcon,
      bgColor: "bg-warning-100",
      textColor: "text-warning-800",
      borderColor: "border-warning-200",
      iconColor: "text-warning-600",
    },
    unknown: {
      label: "Unknown",
      color: "gray",
      icon: QuestionMarkCircleIcon,
      bgColor: "bg-gray-100",
      textColor: "text-gray-800",
      borderColor: "border-gray-200",
      iconColor: "text-gray-600",
    },
  };

  const config = statusConfig[status] || statusConfig.unknown;
  const Icon = config.icon;

  const sizeClasses = {
    sm: "px-2 py-1 text-xs",
    md: "px-2.5 py-1.5 text-sm",
    lg: "px-3 py-2 text-base",
  };

  const iconSizes = {
    sm: "w-3 h-3",
    md: "w-4 h-4",
    lg: "w-5 h-5",
  };

  return (
    <div
      className={clsx(
        "inline-flex items-center rounded-full border font-medium",
        sizeClasses[size],
        config.bgColor,
        config.textColor,
        config.borderColor,
        className
      )}
    >
      {showIcon && (
        <Icon className={clsx("mr-1.5", iconSizes[size], config.iconColor)} />
      )}
      {showText && config.label}
    </div>
  );
};

// Pulse variant for real-time status
export const StatusPulse = ({ status, size = "md" }) => {
  const pulseColors = {
    healthy: "bg-success-500",
    unhealthy: "bg-danger-500",
    warning: "bg-warning-500",
    unknown: "bg-gray-500",
  };

  const pulseSizes = {
    sm: "w-2 h-2",
    md: "w-3 h-3",
    lg: "w-4 h-4",
  };

  return (
    <div className="flex items-center">
      <div
        className={clsx(
          "rounded-full animate-pulse",
          pulseSizes[size],
          pulseColors[status] || pulseColors.unknown
        )}
      />
      <StatusBadge status={status} size={size} className="ml-2" />
    </div>
  );
};

// Dot variant for compact display
export const StatusDot = ({ status, size = "md" }) => {
  const dotColors = {
    healthy: "bg-success-500",
    unhealthy: "bg-danger-500",
    warning: "bg-warning-500",
    unknown: "bg-gray-500",
  };

  const dotSizes = {
    sm: "w-2 h-2",
    md: "w-3 h-3",
    lg: "w-4 h-4",
  };

  return (
    <div
      className={clsx(
        "rounded-full",
        dotSizes[size],
        dotColors[status] || dotColors.unknown
      )}
      title={status}
    />
  );
};

export default StatusBadge;
