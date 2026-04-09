import { useState, useEffect } from "react";
import ChartRenderer from "./components/ChartRenderer";
import LoginPage from "./components/LoginPage";
import { useAuth } from "./contexts/AuthContext";
import { generateVisualization, fetchTables, fetchQuota } from "./services/api";
import "./App.css";

const COMPANIES = [
  { value: "pis", label: "PIS" },
  { value: "igr", label: "IGR" },
  { value: "kingpack", label: "Kingpack" },
];

export default function App() {
  const { user, loading: authLoading, logout } = useAuth();
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Company & Data Mart
  const [selectedCompany, setSelectedCompany] = useState("");
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState("");
  const [tablesLoading, setTablesLoading] = useState(false);

  // Custom dropdown open state
  const [companyDropdownOpen, setCompanyDropdownOpen] = useState(false);
  const [tableDropdownOpen, setTableDropdownOpen] = useState(false);

  // Token quota
  const [quota, setQuota] = useState(null);
  const [showAccessPopup, setShowAccessPopup] = useState(false);

  // Load tables when company changes
  useEffect(() => {
    if (!selectedCompany) {
      setTables([]);
      setSelectedTable("");
      return;
    }
    loadTables(selectedCompany);
  }, [selectedCompany]);

  // Load quota when user logs in
  useEffect(() => {
    if (user) {
      loadQuota();
    }
  }, [user]);

  const loadQuota = async () => {
    try {
      const q = await fetchQuota();
      setQuota(q);
      if (!q.registered) {
        setShowAccessPopup(true);
      }
    } catch (err) {
      console.error("Failed to load quota:", err);
    }
  };

  const loadTables = async (dataset) => {
    setTablesLoading(true);
    setSelectedTable("");
    setTables([]);
    setError("");
    try {
      const res = await fetchTables(dataset);
      setTables(res.tables || []);
    } catch (err) {
      console.error("Failed to load tables:", err);
      setError("Failed to load data marts for this company.");
    } finally {
      setTablesLoading(false);
    }
  };

  const handleCompanySelect = (value) => {
    setSelectedCompany(value);
    setCompanyDropdownOpen(false);
    setSelectedTable("");
    setTableDropdownOpen(false);
    setResult(null);
  };

  const handleTableSelect = (name) => {
    setSelectedTable(name);
    setTableDropdownOpen(false);
    setResult(null);
  };

  const handleGenerate = async () => {
    if (!prompt.trim() || !selectedTable) return;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await generateVisualization(prompt, {
        tableName: selectedTable,
        dataset: selectedCompany,
      });

      if (response.rejected) {
        setError(response.reject_reason || "Request was rejected.");
      } else {
        setResult(response);
        // Update quota from response
        if (response.quota) {
          setQuota(response.quota);
        }
      }
    } catch (err) {
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !loading) {
      e.preventDefault();
      handleGenerate();
    }
  };

  const canGenerate = prompt.trim() && selectedTable && !loading && quota?.registered && quota?.remaining > 0;

  const companyLabel = COMPANIES.find((c) => c.value === selectedCompany)?.label;

  // ─── Auth gate ───
  if (authLoading) {
    return (
      <div className="page-bg">
        <div className="auth-loading">
          <div className="loading-spinner-lg" />
          <p className="loading-text">Checking authentication...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="page-bg">
      <div className="card-container">

        {/* ─── Left Sidebar ─── */}
        <aside className="sidebar">
          {/* User header */}
          <div className="user-header">
            <div className="user-info">
              {user.avatar_url ? (
                <img className="user-avatar" src={user.avatar_url} alt={user.name} />
              ) : (
                <div className="user-avatar-placeholder">
                  {user.name?.charAt(0)?.toUpperCase() || "?"}
                </div>
              )}
              <div className="user-details">
                <span className="user-name">{user.name}</span>
                <span className="user-email">{user.email}</span>
              </div>
            </div>
            <div className="user-actions" style={{ display: 'flex', gap: '0.5rem' }}>
              {quota?.is_admin && (
                <button className="logout-btn" onClick={() => window.location.href = '#/admin'} title="Admin Dashboard">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="3"></circle>
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                  </svg>
                </button>
              )}
              <button className="logout-btn" onClick={logout} title="Logout">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
              </button>
            </div>
          </div>


          {/* Quota bar */}
          {quota?.registered && (
            <div className="quota-bar-container">
              <div className="quota-bar-header">
                <span className="quota-label">Daily Token Quota</span>
                <span className="quota-numbers">
                  {(quota.remaining).toLocaleString()} left
                </span>
              </div>
              <div className="quota-track">
                <div
                  className={`quota-fill ${quota.remaining / quota.daily_limit < 0.1 ? "danger" : quota.remaining / quota.daily_limit < 0.3 ? "warning" : ""}`}
                  style={{ width: `${Math.min(100, (quota.used_today / quota.daily_limit) * 100)}%` }}
                />
              </div>
              <div className="quota-sub">
                {quota.used_today.toLocaleString()} / {quota.daily_limit.toLocaleString()} used
              </div>
            </div>
          )}

          <div className="sidebar-header">
            <span className="sparkle-icon">✨</span>
            <h2 className="sidebar-title">AI Visualization</h2>
          </div>

          <div className="sidebar-body">
            {/* Company Dropdown */}
            <div className="field-group">
              <label className="field-label">Company</label>
              <div className="dropdown-wrapper">
                <button
                  className="dropdown-trigger"
                  onClick={() => { setCompanyDropdownOpen(!companyDropdownOpen); setTableDropdownOpen(false); }}
                >
                  <span className={selectedCompany ? "" : "placeholder"}>
                    {companyLabel || "Select Company"}
                  </span>
                  <svg className={`chevron ${companyDropdownOpen ? "open" : ""}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
                </button>
                {companyDropdownOpen && (
                  <div className="dropdown-menu">
                    {COMPANIES.map((c) => (
                      <button
                        key={c.value}
                        className={`dropdown-item ${selectedCompany === c.value ? "active" : ""}`}
                        onClick={() => handleCompanySelect(c.value)}
                      >
                        {c.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Data Mart Dropdown */}
            <div className="field-group">
              <label className="field-label">Data Mart</label>
              <div className="dropdown-wrapper">
                <button
                  className={`dropdown-trigger ${!selectedCompany || tablesLoading ? "disabled" : ""}`}
                  onClick={() => { if (selectedCompany && !tablesLoading) { setTableDropdownOpen(!tableDropdownOpen); setCompanyDropdownOpen(false); } }}
                  disabled={!selectedCompany || tablesLoading}
                >
                  <span className={selectedTable ? "" : "placeholder"}>
                    {tablesLoading
                      ? "Loading..."
                      : selectedTable
                        ? selectedTable
                        : selectedCompany
                          ? "Select Data Mart"
                          : "Select Company First"}
                  </span>
                  <svg className={`chevron ${tableDropdownOpen ? "open" : ""}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
                </button>
                {tableDropdownOpen && (
                  <div className="dropdown-menu scrollable">
                    {tables.map((t) => (
                      <button
                        key={t.name}
                        className={`dropdown-item ${selectedTable === t.name ? "active" : ""}`}
                        onClick={() => handleTableSelect(t.name)}
                      >
                        <span>{t.name}</span>
                      </button>
                    ))}
                    {tables.length === 0 && (
                      <div className="dropdown-empty">No tables found</div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Prompt */}
            <div className="field-group" style={{ paddingTop: 8 }}>
              <label className="field-label">What would you like to visualize?</label>
              <textarea
                className="prompt-textarea"
                placeholder="e.g., Show me the monthly sales trend for Widget compared to Gadget..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={5}
              />
            </div>

            {/* Generate Button */}
            <button
              className={`generate-btn ${loading ? "loading" : ""}`}
              onClick={handleGenerate}
              disabled={!canGenerate}
            >
              {loading ? (
                <>
                  <span className="spinner" />
                  Generating...
                </>
              ) : (
                <>
                  <span className="btn-sparkle">✨</span>
                  Generate Visualization
                </>
              )}
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="error-box">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* Tip box */}
          <div className="tip-box">
            <strong>Tip:</strong> Be specific about the metrics (e.g., "Revenue", "Count") and time periods you want to analyze.
          </div>
        </aside>

        {/* ─── Right: Visualization Area ─── */}
        <main className="main-area">
          {loading ? (
            <div className="loading-state">
              <div className="loading-spinner-lg" />
              <p className="loading-text">Analyzing data and generating chart...</p>
            </div>
          ) : result?.chart_config?.data?.length > 0 ? (
            <div className="chart-result">
              <ChartRenderer
                chartType={result.chart_type}
                chartConfig={result.chart_config}
              />
              {result.insight && (
                <div className="insight-box">
                  <span className="insight-icon">💡</span>
                  <div>
                    <h4 className="insight-title">AI Generated Insight</h4>
                    <p className="insight-text">{result.insight}</p>
                  </div>
                </div>
              )}
              {result?.token_usage && (
                <div className="token-stats">
                  <div className="token-stat">
                    <span className="token-stat-value">{result.token_usage.prompt_tokens.toLocaleString()}</span>
                    <span className="token-stat-label">Input</span>
                  </div>
                  <div className="token-divider" />
                  <div className="token-stat">
                    <span className="token-stat-value">{result.token_usage.completion_tokens.toLocaleString()}</span>
                    <span className="token-stat-label">Completion</span>
                  </div>
                  <div className="token-divider" />
                  <div className="token-stat">
                    <span className="token-stat-value">{result.token_usage.agent_turns}</span>
                    <span className="token-stat-label">Agent Turn{result.token_usage.agent_turns !== 1 ? "s" : ""}</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state">
              {/* Subtle bar chart placeholder */}
              <div className="empty-bars">
                <div className="bar bar1" />
                <div className="bar bar2" />
                <div className="bar bar3" />
                <div className="bar bar4" />
                <div className="bar bar5" />
              </div>
              <h2 className="empty-title">Visualization Space</h2>
              <p className="empty-subtitle">Select data and enter a prompt to generate insights.</p>
            </div>
          )}
        </main>

      </div>

      {/* Unregistered user popup */}
      {showAccessPopup && (
        <div className="popup-overlay">
          <div className="popup-card">
            <span className="popup-icon">🔒</span>
            <h3 className="popup-title">Access Required</h3>
            <p className="popup-desc">
              Your account (<strong>{user?.email}</strong>) is not registered to use the AI Visualization service.
            </p>
            <p className="popup-desc">
              Please contact the <strong>Data Team</strong> to request access.
            </p>
            <div className="popup-actions">
              <button className="popup-btn-secondary" onClick={() => setShowAccessPopup(false)}>
                Dismiss
              </button>
              <button className="popup-btn-primary" onClick={logout}>
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
