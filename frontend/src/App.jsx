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
  const [messages, setMessages] = useState([]); // { role, content, visualization?, insight?, token_usage?, error? }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");


  // Company & Data Mart
  const [selectedCompany, setSelectedCompany] = useState("");
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState("");
  const [tablesLoading, setTablesLoading] = useState(false);
  const [tableSearch, setTableSearch] = useState("");

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
    setTableSearch("");
    setMessages([]);
  };



  const handleTableSelect = (name) => {
    setSelectedTable(name);
    setTableDropdownOpen(false);
    setTableSearch("");
    setMessages([]);
  };



  const handleGenerate = async () => {
    if (!prompt.trim() || !selectedTable) return;

    const currentPrompt = prompt;
    setPrompt(""); // Clear input early for better UX
    setLoading(true);
    setError("");

    // Add user message to UI
    const userMessage = { role: "user", content: currentPrompt };
    setMessages((prev) => [...prev, userMessage]);

    try {
      // Build history for the backend (excluding current message)
      const history = messages.map(m => ({
        role: m.role,
        content: m.content
      }));

      const response = await generateVisualization(currentPrompt, {
        tableName: selectedTable,
        dataset: selectedCompany,
        history: history
      });

      if (response.rejected) {
        setMessages((prev) => [
          ...prev,
          { 
            role: "model", 
            content: response.reject_reason || "Request was rejected.",
            error: true
          }
        ]);
      } else {
        // Add model response
        setMessages((prev) => [
          ...prev,
          {
            role: "model",
            content: response.insight,
            visualization: {
              type: response.chart_type,
              config: response.chart_config
            },
            insight: response.insight,
            token_usage: response.token_usage
          }
        ]);

        // Update quota
        if (response.quota) {
          setQuota(response.quota);
        }
      }
    } catch (err) {
      setError(err.message || "An unexpected error occurred.");
      setMessages((prev) => [
        ...prev,
        { role: "model", content: err.message || "Error occurred", error: true }
      ]);
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
      <div className="chat-container">
        {/* ─── Left Sidebar (Config & Quota) ─── */}
        <aside className="chat-sidebar">
          <div className="sidebar-top">
            <div className="sidebar-brand">
              <span className="sparkle-icon">✨</span>
              <h1 className="sidebar-title">VizAgent</h1>
            </div>

            {/* Quota bar */}
            {quota?.registered && (
              <div className="quota-widget">
                <div className="quota-header">
                  <span>Quota</span>
                  <span className="quota-val">{(quota.remaining).toLocaleString()}</span>
                </div>
                <div className="quota-track">
                  <div
                    className={`quota-fill ${quota.remaining / quota.daily_limit < 0.1 ? "danger" : quota.remaining / quota.daily_limit < 0.3 ? "warning" : ""}`}
                    style={{ width: `${Math.min(100, (quota.used_today / quota.daily_limit) * 100)}%` }}
                  />
                </div>
              </div>
            )}

            <div className="sidebar-divider" />

            <div className="sidebar-sections">
              {/* Company Dropdown */}
              <div className="config-section">
                <label>Company</label>
                <div className="dropdown-wrapper">
                  <button
                    className="dropdown-trigger"
                    onClick={() => { setCompanyDropdownOpen(!companyDropdownOpen); setTableDropdownOpen(false); }}
                  >
                    <span>{companyLabel || "Select..."}</span>
                    <svg className={`chevron ${companyDropdownOpen ? "open" : ""}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
                  </button>
                  {companyDropdownOpen && (
                    <div className="dropdown-menu">
                      {COMPANIES.map((c) => (
                        <button key={c.value} className="dropdown-item" onClick={() => handleCompanySelect(c.value)}>{c.label}</button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Data Mart Dropdown */}
              <div className="config-section">
                <label>Data Mart</label>
                <div className="dropdown-wrapper">
                  <button
                    className={`dropdown-trigger ${!selectedCompany || tablesLoading ? "disabled" : ""}`}
                    onClick={() => { if (selectedCompany && !tablesLoading) { setTableDropdownOpen(!tableDropdownOpen); setCompanyDropdownOpen(false); } }}
                    disabled={!selectedCompany || tablesLoading}
                  >
                    <span>{tablesLoading ? "Loading..." : selectedTable || "Select..."}</span>
                    <svg className={`chevron ${tableDropdownOpen ? "open" : ""}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
                  </button>
                  {tableDropdownOpen && (
                    <div className="dropdown-menu scrollable">
                      <div className="dropdown-search-wrapper">
                        <input
                          type="text"
                          className="dropdown-search-input"
                          placeholder="Search tables..."
                          value={tableSearch}
                          onChange={(e) => setTableSearch(e.target.value)}
                          autoFocus
                          onClick={(e) => e.stopPropagation()}
                        />
                      </div>
                      <div className="dropdown-items-container">
                        {tables.filter(t => t.name.toLowerCase().includes(tableSearch.toLowerCase())).map((t) => (
                          <button key={t.name} className="dropdown-item" onClick={() => handleTableSelect(t.name)}>{t.name}</button>
                        ))}
                        {tables.filter(t => t.name.toLowerCase().includes(tableSearch.toLowerCase())).length === 0 && (
                          <div className="dropdown-no-results">No tables found.</div>
                        )}
                      </div>
                    </div>
                  )}

                </div>
              </div>
            </div>
          </div>

          <div className="sidebar-bottom">
            <div className="user-pill">
              <img className="user-avatar" src={user.avatar_url || "https://ui-avatars.com/api/?name="+user.name} alt={user.name} />
              <div className="user-info-min">
                <span className="user-name-min">{user.name}</span>
                {quota?.is_admin && <span className="admin-tag">Admin</span>}
              </div>
              <div className="user-actions-row">
                {quota?.is_admin && (
                   <button className="icon-btn" onClick={() => window.location.href = '#/admin'} title="Admin">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                   </button>
                )}
                <button className="icon-btn logout" onClick={logout} title="Logout">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
                </button>
              </div>
            </div>
          </div>
        </aside>

        {/* ─── Main Chat Area ─── */}
        <main className="chat-main">
          <div className="messages-scroller">
            {messages.length === 0 ? (
              <div className="chat-empty-state">
                <div className="welcome-hero">
                  <div className="hero-icon">📊</div>
                  <h2>Intelligence at your fingertips</h2>
                  <p>Select a <strong>Data Mart</strong> and ask me anything about your data.</p>
                </div>
                <div className="suggestion-grid">
                  <div className="suggestion-card" onClick={() => setPrompt("Show me daily sales trends")}>
                    <span>📈</span> daily sales trends
                  </div>
                  <div className="suggestion-card" onClick={() => setPrompt("Top 5 products by revenue")}>
                    <span>🏆</span> top 5 products
                  </div>
                  <div className="suggestion-card" onClick={() => setPrompt("Monthly distribution of orders")}>
                    <span>📅</span> monthly distribution
                  </div>
                </div>
              </div>
            ) : (
              <div className="messages-list">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`message-row ${msg.role}`}>
                    <div className="message-bubble">
                      {msg.role === 'user' ? (
                        <div className="user-message-text">{msg.content}</div>
                      ) : (
                        <div className="model-message-content">
                          {msg.visualization && (
                            <div className="message-chart">
                              <ChartRenderer
                                chartType={msg.visualization.type}
                                chartConfig={msg.visualization.config}
                              />
                            </div>
                          )}
                          <div className="message-insight">
                            {msg.content}
                          </div>
                          {msg.token_usage && (
                             <div className="message-meta">
                               {msg.token_usage.total_tokens.toLocaleString()} tokens
                             </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {loading && (
                   <div className="message-row model">
                     <div className="message-bubble loading-bubble">
                       <span className="dot-typing"></span>
                     </div>
                   </div>
                )}
                {error && <div className="chat-error-toast">{error}</div>}
              </div>
            )}
          </div>

          {/* Bottom Input Area */}
          <div className="chat-input-wrapper">
            <div className="chat-input-container">
              <textarea
                className="chat-textarea"
                placeholder={selectedTable ? "Ask a question or follow up..." : "Select a Data Mart first..."}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={!selectedTable || loading}
                rows={1}
              />
              <button
                className="chat-send-btn"
                onClick={handleGenerate}
                disabled={!canGenerate}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
              </button>
            </div>
            <p className="chat-disclaimer">VizAgent may refine previous results based on your context.</p>
          </div>
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
