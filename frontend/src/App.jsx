import { useState, useEffect } from "react";
import ChartRenderer from "./components/ChartRenderer";
import { generateVisualization, fetchTables } from "./services/api";
import "./App.css";

const COMPANIES = [
  { value: "pis", label: "PIS" },
  { value: "igr", label: "IGR" },
  { value: "kingpack", label: "Kingpack" },
];

export default function App() {
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

  // Load tables when company changes
  useEffect(() => {
    if (!selectedCompany) {
      setTables([]);
      setSelectedTable("");
      return;
    }
    loadTables(selectedCompany);
  }, [selectedCompany]);

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

  const canGenerate = prompt.trim() && selectedTable && !loading;

  const companyLabel = COMPANIES.find((c) => c.value === selectedCompany)?.label;

  return (
    <div className="page-bg">
      <div className="card-container">

        {/* ─── Left Sidebar ─── */}
        <aside className="sidebar">
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
    </div>
  );
}
