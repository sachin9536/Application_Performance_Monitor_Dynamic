import React, { createContext, useContext, useState, useEffect } from "react";
import { apiService, api } from "./services/api";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem("jwt") || null);
  const [loading, setLoading] = useState(false);

  // Attach token to all API requests
  useEffect(() => {
    if (token) {
      localStorage.setItem("jwt", token);
      apiService.setAuthToken(token);
    } else {
      localStorage.removeItem("jwt");
      apiService.setAuthToken(null);
    }
  }, [token]);

  // Optionally, decode user info from JWT
  useEffect(() => {
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        setUser({ email: payload.email });
      } catch {
        setUser(null);
      }
    } else {
      setUser(null);
    }
  }, [token]);

  const login = async (email, password) => {
    setLoading(true);
    try {
      const res = await apiService.loginUser({ email, password });
      if (res.access_token) {
        setToken(res.access_token);
        setUser({ email });
        return { success: true };
      } else {
        throw new Error(res.msg || "Login failed");
      }
    } catch (e) {
      setToken(null);
      setUser(null);
      return { success: false, error: e.message };
    } finally {
      setLoading(false);
    }
  };

  const register = async (email, password) => {
    setLoading(true);
    try {
      const res = await apiService.registerUser({ email, password });
      if (res.status === "success") {
        // Optionally auto-login after register
        return await login(email, password);
      } else {
        throw new Error(res.msg || "Registration failed");
      }
    } catch (e) {
      return { success: false, error: e.message };
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, token, loading, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

// Add setAuthToken to apiService
if (!apiService.setAuthToken) {
  apiService.setAuthToken = (token) => {
    if (token) {
      api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    } else {
      delete api.defaults.headers.common["Authorization"];
    }
  };
}
