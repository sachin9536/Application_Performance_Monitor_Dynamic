import React, { useState, useEffect } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { Toaster } from "react-hot-toast";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import Dashboard from "./pages/Dashboard";
import Services from "./pages/Services";
import Logs from "./pages/Logs";
import Metrics from "./pages/Metrics";
import Analytics from "./pages/Analytics";
import ServiceDetails from "./pages/ServiceDetails";
import DatabaseManagement from "./pages/DatabaseManagement";
import { MoonIcon, SunIcon } from "@heroicons/react/24/outline";
import { AuthProvider, useAuth } from "./AuthContext";
import Welcome from "./pages/Welcome";
import Login from "./pages/Login";
import Register from "./pages/Register";
import LoadForecast from "./pages/LoadForecast";

function AuthLayout({ children }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 dark:bg-gray-900 animate-fadeIn">
      {children}
    </div>
  );
}

function AppLayout({
  children,
  sidebarOpen,
  setSidebarOpen,
  isDarkMode,
  setIsDarkMode,
}) {
  return (
    <div
      className={`h-screen flex overflow-hidden bg-gray-50 dark:bg-gray-900 dark:text-gray-100`}
    >
      {/* Sidebar */}
      <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />
      {/* Main content */}
      <div className="flex flex-col w-0 flex-1 overflow-hidden">
        {/* Header */}
        <div className="relative">
          <Header onMenuClick={() => setSidebarOpen(true)} />
          {/* Dark mode toggle button */}
          <button
            className="absolute top-4 right-4 z-50 p-2 rounded-full bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
            onClick={() => setIsDarkMode((d) => !d)}
            title={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
          >
            {isDarkMode ? (
              <SunIcon className="w-5 h-5 text-yellow-400" />
            ) : (
              <MoonIcon className="w-5 h-5 text-gray-700" />
            )}
          </button>
        </div>
        {/* Main content area */}
        <main className="flex-1 relative overflow-y-auto focus:outline-none">
          <div className="py-6">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8">
              {children}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function ProtectedRoute({ children }) {
  const { token } = useAuth();
  const location = useLocation();
  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
}

function AppRoutes({ sidebarOpen, setSidebarOpen, isDarkMode, setIsDarkMode }) {
  const { token } = useAuth();
  return (
    <Routes>
      {/* Redirect root to dashboard if logged in, else to welcome */}
      <Route
        path="/"
        element={
          token ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <Navigate to="/welcome" replace />
          )
        }
      />
      {/* Auth pages - no sidebar/header */}
      <Route
        path="/welcome"
        element={
          <AuthLayout>
            <Welcome />
          </AuthLayout>
        }
      />
      <Route
        path="/login"
        element={
          <AuthLayout>
            <Login />
          </AuthLayout>
        }
      />
      <Route
        path="/register"
        element={
          <AuthLayout>
            <Register />
          </AuthLayout>
        }
      />
      {/* Main app - protected, with sidebar/header */}
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <AppLayout
              sidebarOpen={sidebarOpen}
              setSidebarOpen={setSidebarOpen}
              isDarkMode={isDarkMode}
              setIsDarkMode={setIsDarkMode}
            >
              <Routes>
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="services" element={<Services />} />
                <Route path="services/:name" element={<ServiceDetails />} />
                <Route path="logs" element={<Logs />} />
                <Route path="metrics" element={<Metrics />} />
                <Route path="analytics" element={<Analytics />} />
                <Route path="databases" element={<DatabaseManagement />} />
                <Route path="load-forecast" element={<LoadForecast />} />
              </Routes>
            </AppLayout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    // Load from localStorage or default to false
    return localStorage.getItem("darkMode") === "true";
  });

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    localStorage.setItem("darkMode", isDarkMode);
  }, [isDarkMode]);

  return (
    <AuthProvider>
      <Router>
        <AppRoutes
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          isDarkMode={isDarkMode}
          setIsDarkMode={setIsDarkMode}
        />
        {/* Toast notifications */}
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: isDarkMode ? "#222" : "#363636",
              color: "#fff",
            },
            success: {
              duration: 3000,
              iconTheme: {
                primary: "#22c55e",
                secondary: "#fff",
              },
            },
            error: {
              duration: 5000,
              iconTheme: {
                primary: "#ef4444",
                secondary: "#fff",
              },
            },
          }}
        />
      </Router>
    </AuthProvider>
  );
}

export default App;
