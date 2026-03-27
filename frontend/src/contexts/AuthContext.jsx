/**
 * Auth context for Lark SSO authentication.
 *
 * Provides user state, loading state, and login/logout actions
 * to the entire application via React Context.
 */

import { createContext, useContext, useState, useEffect } from "react";

const API_BASE =
  import.meta.env.VITE_API_URL ||
  "https://prompt2viz-backend-767416511940.asia-southeast2.run.app";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On mount, check if we have a valid session
  useEffect(() => {
    checkAuth();
  }, []);

  async function checkAuth() {
    try {
      const response = await fetch(`${API_BASE}/api/auth/me`, {
        credentials: "include",
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data.user);
      } else {
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
    // Redirect the browser to the backend login endpoint,
    // which will redirect to Lark's OAuth page
    window.location.href = `${API_BASE}/api/auth/login`;
  }

  async function logout() {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch (err) {
      console.error("Logout error:", err);
    }
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
