import React, { useEffect, useState } from "react";
import { apiService } from "../services/api";
import StatusBadge from "../components/StatusBadge";

const DatabaseManagement = () => {
  const [databases, setDatabases] = useState([]);
  const [counts, setCounts] = useState({
    total: 0,
    connected: 0,
    disconnected: 0,
  });
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", uri: "", type: "mongodb" });
  const dbTypes = [
    { value: "mongodb", label: "MongoDB" },
    { value: "postgresql", label: "PostgreSQL" },
    { value: "mysql", label: "MySQL" },
  ];
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  const fetchDatabases = async () => {
    setLoading(true);
    try {
      const data = await apiService.getDatabases();
      setDatabases(data.databases);
      // Calculate counts from the databases array
      const connected = data.databases.filter(
        (db) => db.status === "connected"
      ).length;
      const disconnected = data.databases.filter(
        (db) => db.status !== "connected"
      ).length;
      setCounts({
        total: data.databases.length,
        connected,
        disconnected,
      });
    } catch (e) {
      setError("Failed to load databases");
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchDatabases();
    const interval = setInterval(fetchDatabases, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleInputChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleAddDatabase = async (e) => {
    e.preventDefault();
    setAdding(true);
    setError("");
    try {
      const res = await apiService.addDatabase(form);
      if (res.status === "success" || res.success) {
        setForm({ name: "", uri: "", type: "mongodb" });
        fetchDatabases();
      } else {
        setError(res.message || res.error || "Failed to add database");
      }
    } catch (e) {
      // Try to show backend error message if available
      setError(
        e?.response?.data?.message || e?.message || "Failed to add database"
      );
    }
    setAdding(false);
  };

  const handleTestConnection = async (e) => {
    e.preventDefault();
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiService.testDatabaseConnection({
        type: form.type,
        uri: form.uri,
      });
      setTestResult(res);
    } catch (err) {
      setTestResult({
        success: false,
        message: err?.response?.data?.message || err.message || "Test failed",
      });
    }
    setTesting(false);
  };

  const handleRemoveDatabase = async (name) => {
    if (!window.confirm(`Remove database '${name}'?`)) return;
    try {
      await apiService.removeDatabase(name);
      fetchDatabases();
    } catch (e) {
      setError("Failed to remove database");
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-4">
      <h1 className="text-3xl font-bold mb-6 text-primary-700">
        Database Management
      </h1>
      <div className="flex flex-col md:flex-row gap-6 mb-8">
        <div className="flex-1 bg-white rounded-xl shadow-md p-6 border border-gray-100">
          <h2 className="text-xl font-semibold mb-4">Status Overview</h2>
          <div className="flex gap-8 mb-2">
            <div>
              <span className="text-2xl font-bold text-gray-900">
                {counts.total}
              </span>
              <div className="text-xs text-gray-500 uppercase">Total</div>
            </div>
            <div>
              <span className="text-2xl font-bold text-success-600">
                {counts.connected}
              </span>
              <div className="text-xs text-success-700 uppercase">
                Connected
              </div>
            </div>
            <div>
              <span className="text-2xl font-bold text-danger-600">
                {counts.disconnected}
              </span>
              <div className="text-xs text-danger-700 uppercase">
                Disconnected
              </div>
            </div>
          </div>
        </div>
        <div className="flex-1 bg-white rounded-xl shadow-md p-6 border border-gray-100">
          <h2 className="text-xl font-semibold mb-4">Add New Database</h2>
          <form onSubmit={handleAddDatabase} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Database Type
              </label>
              <select
                name="type"
                value={form.type}
                onChange={handleInputChange}
                className="input w-full"
                required
              >
                {dbTypes.map((db) => (
                  <option key={db.value} value={db.value}>
                    {db.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Database Name
              </label>
              <input
                type="text"
                name="name"
                value={form.name}
                onChange={handleInputChange}
                className="input w-full"
                placeholder="Enter database name"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                {form.type === "mongodb"
                  ? "MongoDB URI"
                  : form.type === "postgresql"
                  ? "PostgreSQL URI"
                  : "MySQL URI"}
              </label>
              <input
                type="text"
                name="uri"
                value={form.uri}
                onChange={handleInputChange}
                className="input w-full"
                placeholder={
                  form.type === "mongodb"
                    ? "mongodb://username:password@host:port/dbname"
                    : form.type === "postgresql"
                    ? "postgresql://username:password@host:port/dbname"
                    : "mysql://username:password@host:port/dbname"
                }
                required
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn btn-secondary flex-1"
                onClick={handleTestConnection}
                disabled={testing || !form.uri || !form.type}
              >
                {testing ? "Testing..." : "Test Connection"}
              </button>
              <button
                type="submit"
                className="btn btn-primary flex-1"
                disabled={adding || (testResult && !testResult.success)}
              >
                {adding ? "Adding..." : "Add Database"}
              </button>
            </div>
            {testResult && (
              <div
                className={
                  testResult.success
                    ? "text-success-700 text-sm"
                    : "text-danger-600 text-sm"
                }
              >
                {testResult.message}
              </div>
            )}
            {error && <div className="text-danger-600 text-sm">{error}</div>}
          </form>
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-6">
        {loading ? (
          <div className="col-span-2 text-center text-gray-500">
            Loading databases...
          </div>
        ) : databases.length === 0 ? (
          <div className="col-span-2 text-center text-gray-500">
            No databases registered yet.
          </div>
        ) : (
          databases.map((db) => (
            <div
              key={db.name}
              className={`rounded-xl shadow-md border p-6 mb-2 bg-white flex flex-col gap-2 border-l-8 ${
                db.status === "connected"
                  ? "border-success-400"
                  : "border-danger-400"
              } animate-fadeIn`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="font-bold text-lg text-primary-700">
                  {db.name}
                  <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-700 border border-gray-200">
                    {db.type
                      ? db.type.charAt(0).toUpperCase() + db.type.slice(1)
                      : ""}
                  </span>
                </div>
                <StatusBadge
                  status={db.status === "connected" ? "healthy" : "error"}
                  showText
                />
              </div>
              <div className="text-xs text-gray-500 mb-1">{db.uri}</div>
              {db.status === "connected" ? (
                <div className="text-sm text-success-700 mb-1">
                  Response Time:{" "}
                  {db.response_time_ms !== undefined &&
                  db.response_time_ms !== null
                    ? db.response_time_ms + " ms"
                    : "N/A"}
                  <br />
                  Host: {db.host || "-"} <br />
                  Port: {db.port || "-"}
                </div>
              ) : (
                <div className="text-sm text-danger-700 mb-1">
                  Error: {db.error || "Unknown error"}
                </div>
              )}
              <div className="text-xs text-gray-400 mt-1">
                Last checked:{" "}
                {db.last_checked
                  ? new Date(db.last_checked).toLocaleString()
                  : "N/A"}
              </div>
              <button
                className="btn btn-danger btn-sm mt-2 self-end"
                onClick={() => handleRemoveDatabase(db.name)}
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default DatabaseManagement;
