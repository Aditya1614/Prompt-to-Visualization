/**
 * Login page / access denied gate.
 *
 * Shown when the user is not authenticated via Lark SSO.
 * Styled consistently with the app's dark theme.
 */

import { useAuth } from "../contexts/AuthContext";
import "./LoginPage.css";


export default function LoginPage() {
  const { login } = useAuth();

  // Check for auth error in URL params (e.g., user denied access)
  const params = new URLSearchParams(window.location.search);
  const authError = params.get("auth_error");

  return (
    <div className="login-page">
      <div className="login-card">
        {/* Brand header */}
        <div className="login-brand">
          <span className="login-sparkle">✨</span>
          <h1 className="login-title">
            VizAgentAI <span className="beta-badge">Beta</span>
          </h1>
          <p className="login-subtitle">
            Developed by IT Data Analyst Team · Powered by Gemini
          </p>
        </div>

        {/* Divider */}
        <div className="login-divider" />

        {/* Access denied message */}
        <div className="login-message">
          {authError === "access_denied" ? (
            <>
              <span className="login-icon-denied">🚫</span>
              <h2 className="login-heading">Access Denied</h2>
              <p className="login-desc">
                You declined the authorization request. Please login with your
                Lark account to use this application.
              </p>
            </>
          ) : (
            <>
              <span className="login-icon-lock">🔒</span>
              <h2 className="login-heading">Authentication Required</h2>
              <p className="login-desc">
                Sign in with your Lark account to access the visualization
                dashboard.
              </p>
            </>
          )}
        </div>

        {/* Login button */}
        <button className="login-btn" onClick={login}>
          <svg
            className="lark-icon"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
            <polyline points="10 17 15 12 10 7" />
            <line x1="15" y1="12" x2="3" y2="12" />
          </svg>
          Login with Lark
        </button>

        <p className="login-footer">
          Only authorized Lark workspace members can access this application.
        </p>
      </div>
    </div>
  );
}
