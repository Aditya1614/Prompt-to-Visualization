/**
 * Auth context for Lark SSO authentication.
 *
 * Uses localStorage + Authorization Bearer header instead of cookies
 * to avoid cross-domain cookie issues (Firebase ↔ Cloud Run).
 */

import { createContext, useContext, useState, useEffect } from "react";

const API_BASE =
  import.meta.env.VITE_API_URL ||
  "https://prompt2viz-backend-767416511940.asia-southeast2.run.app";

const TOKEN_KEY = "lark_session_token";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if there's a token in the URL hash (from OAuth callback redirect)
    const hash = window.location.hash;
    if (hash.startsWith("#token=")) {
      const token = hash.substring(7); // Remove "#token="
      localStorage.setItem(TOKEN_KEY, token);
      // Clean the URL hash
      window.history.replaceState(null, "", window.location.pathname);
    }

    checkAuth();
  }, []);

  async function checkAuth() {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data.user);
      } else {
        // Token is invalid/expired — clear it
        localStorage.removeItem(TOKEN_KEY);
        setUser(null);
      }
    } catch (err) {
      console.error("Auth check failed:", err);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  function login() {
    window.location.href = `${API_BASE}/api/auth/login`;
  }

  async function logout() {
    const token = localStorage.getItem(TOKEN_KEY);
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch (err) {
      console.error("Logout error:", err);
    }
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

/**
 * Get the current auth token from localStorage.
 * Used by api.js to attach Bearer token to requests.
 */
export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}
