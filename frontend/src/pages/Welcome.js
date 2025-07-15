import React from "react";
import { Link } from "react-router-dom";
import {
  CheckCircleIcon,
  ChartBarIcon,
  CpuChipIcon,
  ShieldCheckIcon,
  BoltIcon,
  EyeIcon,
} from "@heroicons/react/24/solid";

const Welcome = () => (
  <div className="min-h-screen w-full flex items-center justify-center bg-gradient-to-br from-blue-100 via-indigo-100 to-purple-100 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 relative overflow-hidden">
    {/* Decorative Blobs */}
    <div className="absolute left-0 top-0 h-full w-1/3 flex items-center justify-center pointer-events-none z-0">
      <div className="w-96 h-96 bg-blue-300 rounded-full filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
    </div>
    <div className="absolute right-0 bottom-0 h-full w-1/3 flex items-center justify-center pointer-events-none z-0">
      <div className="w-96 h-96 bg-purple-300 rounded-full filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
    </div>
    {/* Centered Welcome Card */}
    <div className="relative z-10 flex flex-col items-center justify-center w-full min-h-screen px-4">
      <div className="w-full max-w-5xl mx-auto glass shadow-2xl rounded-3xl p-12 border border-gray-200/60 dark:border-gray-700/60 backdrop-blur-md">
        {/* Main content */}
        <div className="w-full max-w-4xl mx-auto text-center mb-12">
          {/* Logo and title */}
          <div className="flex items-center justify-center mb-8">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl blur-lg opacity-75"></div>
              <div className="relative bg-white dark:bg-gray-800 rounded-2xl p-4 shadow-2xl border border-gray-100 dark:border-gray-700">
                <CheckCircleIcon className="w-12 h-12 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
            <span className="ml-4 text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              AppVital
            </span>
          </div>

          <h1 className="text-6xl md:text-7xl font-extrabold mb-6 bg-gradient-to-r from-gray-900 via-blue-800 to-purple-800 dark:from-white dark:via-blue-200 dark:to-purple-200 bg-clip-text text-transparent leading-tight">
            Monitor. Analyze.
            <br />
            <span className="text-blue-600 dark:text-blue-400">Optimize.</span>
          </h1>

          <p className="text-xl md:text-2xl text-gray-600 dark:text-gray-300 mb-12 max-w-3xl mx-auto leading-relaxed">
            Your all-in-one Application Performance Monitoring platform.
            <span className="font-semibold text-blue-600 dark:text-blue-400">
              {" "}
              Real-time insights
            </span>{" "}
            for modern applications.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-6 justify-center mb-16">
            <Link
              to="/register"
              className="group relative px-8 py-4 rounded-2xl text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-2xl hover:shadow-blue-500/25 transition-all duration-300 transform hover:scale-105 hover:-translate-y-1"
            >
              <span className="relative z-10">Get Started</span>
              <div className="absolute inset-0 bg-gradient-to-r from-blue-700 to-purple-700 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            </Link>
            <Link
              to="/login"
              className="group px-8 py-4 rounded-2xl text-xl font-bold bg-white dark:bg-gray-800 text-gray-900 dark:text-white border-2 border-gray-200 dark:border-gray-600 shadow-xl hover:shadow-2xl transition-all duration-300 transform hover:scale-105 hover:-translate-y-1"
            >
              Sign In
              <span className="ml-2 text-blue-600 dark:text-blue-400 group-hover:translate-x-1 transition-transform duration-300">
                →
              </span>
            </Link>
          </div>
        </div>

        {/* Features Grid */}
        <div className="w-full max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12 text-gray-900 dark:text-white">
            Everything you need for modern application monitoring
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-16">
            {[
              {
                icon: ChartBarIcon,
                title: "Real-time Metrics",
                description:
                  "Monitor performance, errors, and system health with millisecond precision",
                color: "blue",
              },
              {
                icon: CpuChipIcon,
                title: "AI-Powered Analytics",
                description:
                  "Advanced root cause analysis and intelligent anomaly detection",
                color: "purple",
              },
              {
                icon: ShieldCheckIcon,
                title: "Secure & Reliable",
                description:
                  "Enterprise-grade security with JWT authentication and encrypted data",
                color: "green",
              },
              {
                icon: BoltIcon,
                title: "Lightning Fast",
                description:
                  "Optimized for speed with real-time updates and instant alerts",
                color: "yellow",
              },
              {
                icon: EyeIcon,
                title: "Visual Insights",
                description:
                  "Beautiful dashboards and charts for comprehensive system visibility",
                color: "indigo",
              },
              {
                icon: CheckCircleIcon,
                title: "Easy Integration",
                description:
                  "Simple setup with automatic service discovery and monitoring",
                color: "emerald",
              },
            ].map((feature, index) => (
              <div
                key={index}
                className="group bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-2xl p-8 border border-gray-200/50 dark:border-gray-700/50 shadow-xl hover:shadow-2xl transition-all duration-300 transform hover:scale-105 hover:-translate-y-2"
              >
                <div
                  className={`inline-flex p-4 rounded-2xl bg-${feature.color}-100 dark:bg-${feature.color}-900/20 mb-6 group-hover:scale-110 transition-transform duration-300`}
                >
                  <feature.icon
                    className={`w-8 h-8 text-${feature.color}-600 dark:text-${feature.color}-400`}
                  />
                </div>
                <h3 className="text-xl font-bold mb-3 text-gray-900 dark:text-white">
                  {feature.title}
                </h3>
                <p className="text-gray-600 dark:text-gray-300 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom CTA */}
        <div className="text-center">
          <p className="text-lg text-gray-600 dark:text-gray-300 mb-6">
            Ready to transform your application monitoring?
          </p>
          <Link
            to="/register"
            className="inline-flex items-center px-6 py-3 rounded-xl text-lg font-semibold bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105"
          >
            Start Monitoring Today
            <CheckCircleIcon className="ml-2 w-5 h-5" />
          </Link>
        </div>
      </div>
    </div>
  </div>
);

export default Welcome;
