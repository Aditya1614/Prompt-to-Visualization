import { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import { Link, Navigate } from "react-router-dom";
import { 
    fetchOrgUsers, fetchQuotaSettings, updateUserQuota, removeUserQuota, fetchQuota, setAdminRole,
    fetchAdminDatamarts, syncAdminDatamarts, updateDatamartAccess
} from "../services/api";
import "./AdminPage.css";

export default function AdminPage() {
    const { user, loading: authLoading } = useAuth();
    const [isAdmin, setIsAdmin] = useState(false);
    const [adminLoading, setAdminLoading] = useState(true);

    const [orgUsers, setOrgUsers] = useState([]);
    const [quotaUsers, setQuotaUsers] = useState([]);
    
    const [orgLoading, setOrgLoading] = useState(false);
    const [quotaLoading, setQuotaLoading] = useState(false);
    const [datamartsLoading, setDatamartsLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    
    // Datamart state
    const [datamarts, setDatamarts] = useState([]);

    // Edit state
    const [editingEmail, setEditingEmail] = useState(null);
    const [editLimit, setEditLimit] = useState("");
    
    // Dropdown state
    const [openRoleDropdown, setOpenRoleDropdown] = useState(null);

    // Check admin status
    useEffect(() => {
        if (!user) return;
        
        async function checkAdmin() {
            try {
                const q = await fetchQuota();
                setIsAdmin(q.is_admin === true);
            } catch (err) {
                console.error("Admin check failed", err);
            } finally {
                setAdminLoading(false);
            }
        }
        checkAdmin();
    }, [user]);

    // Load initial data
    useEffect(() => {
        if (isAdmin) {
            loadQuotaSettings();
            loadDatamarts();
        }
    }, [isAdmin]);

    const loadDatamarts = async () => {
        setDatamartsLoading(true);
        try {
            const data = await fetchAdminDatamarts();
            setDatamarts(data.datamarts || []);
        } catch (err) {
            console.error("Failed to load datamarts", err);
        } finally {
            setDatamartsLoading(false);
        }
    };

    const handleSyncDatamarts = async () => {
        setDatamartsLoading(true);
        try {
            await syncAdminDatamarts();
            loadDatamarts();
        } catch (err) {
            alert(`Failed to sync datamarts: ${err.message}`);
            setDatamartsLoading(false);
        }
    };
    
    const handleUpdateDatamartAccess = async (dataset, table, selectElement) => {
        const options = Array.from(selectElement.selectedOptions);
        const selectedEmails = options.map(opt => opt.value);
        try {
            await updateDatamartAccess(dataset, table, selectedEmails);
            loadDatamarts();
        } catch (err) {
            alert(`Failed to update access: ${err.message}`);
        }
    };

    const loadQuotaSettings = async () => {
        setQuotaLoading(true);
        try {
            const data = await fetchQuotaSettings();
            setQuotaUsers(data.users || []);
        } catch (err) {
            console.error(err);
            alert("Failed to load quota settings.");
        } finally {
            setQuotaLoading(false);
        }
    };

    const handleSyncOrg = async () => {
        setOrgLoading(true);
        try {
            const data = await fetchOrgUsers();
            setOrgUsers(data.users || []);
        } catch (err) {
            console.error(err);
            alert(`Failed to sync org users: ${err.message}`);
        } finally {
            setOrgLoading(false);
        }
    };

    const handleGrantAccess = async (orgUser) => {
        try {
            // Default limit 100k
            await updateUserQuota(orgUser.email, orgUser.name, 100000);
            loadQuotaSettings();
        } catch (err) {
            console.error(err);
            alert("Failed to grant access.");
        }
    };

    const handleSaveLimit = async (email, name) => {
        try {
            await updateUserQuota(email, name, parseInt(editLimit, 10));
            setEditingEmail(null);
            loadQuotaSettings();
        } catch (err) {
            console.error(err);
            alert("Failed to update limit.");
        }
    };

    const handleRemoveAccess = async (email) => {
        if (!window.confirm(`Are you sure you want to remove access for ${email}?`)) return;
        try {
            await removeUserQuota(email);
            loadQuotaSettings();
        } catch (err) {
            console.error(err);
            alert("Failed to remove user.");
        }
    };

    const handleSetAdmin = async (email, isAdminStatus) => {
        const action = isAdminStatus ? "promote to Admin" : "revoke Admin rights from";
        if (!window.confirm(`Are you sure you want to ${action} ${email}?`)) return;
        try {
            await setAdminRole(email, isAdminStatus);
            loadQuotaSettings();
        } catch (err) {
            console.error(err);
            alert(`Failed to update admin role. ${err.message || ''}`);
        }
    };

    if (authLoading || adminLoading) {
        return (
            <div className="page-bg">
                <div className="auth-loading">
                    <div className="loading-spinner-lg" />
                    <p className="loading-text">Verifying permissions...</p>
                </div>
            </div>
        );
    }

    if (!user || !isAdmin) {
        return <Navigate to="/" />;
    }

    const filteredOrgUsers = orgUsers.filter(u => 
        u.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
        u.email.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const totalUsers = quotaUsers.length;
    const activeToday = quotaUsers.filter(u => u.used_today > 0).length;
    const totalTokens = quotaUsers.reduce((sum, u) => sum + u.used_today, 0);

    return (
        <div className="page-bg">
            <div className="card-container" style={{ flexDirection: 'column', maxWidth: '1100px' }}>
                <div className="admin-page">
                    <header className="admin-header">
                <div>
                    <h1 className="admin-title">Organization Access Control</h1>
                    <p className="admin-subtitle">Manage token quotas and AI Visualization access</p>
                </div>
                <div className="admin-header-actions">
                    <span className="admin-badge">Admin Mode</span>
                    <Link to="/" className="back-btn">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
                        Back to App
                    </Link>
                </div>
            </header>

            <div className="admin-stats">
                <div className="stat-card">
                    <div className="stat-label">Registered Users</div>
                    <div className="stat-value">{totalUsers}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Active Today</div>
                    <div className="stat-value">{activeToday}</div>
                </div>
                <div className="stat-card stat-primary">
                    <div className="stat-label">Total Tokens Used (Today)</div>
                    <div className="stat-value">{totalTokens.toLocaleString()}</div>
                </div>
            </div>

            <div className="admin-grid">
                {/* ─── Registered Users Panel ─── */}
                <div className="admin-panel full-width">
                    <div className="panel-header">
                        <h2>Registered Users ({quotaUsers.length})</h2>
                        <button className="panel-btn" onClick={loadQuotaSettings} disabled={quotaLoading}>
                            {quotaLoading ? "Loading..." : "Refresh"}
                        </button>
                    </div>
                    <div className="table-container">
                        <table className="admin-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Email</th>
                                    <th>Role</th>
                                    <th style={{width: '200px'}}>Daily Limit</th>
                                    <th>Used Today</th>
                                    <th>Usage Bar</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {quotaUsers.length === 0 ? (
                                    <tr><td colSpan="7" className="empty-table">No users registered yet</td></tr>
                                ) : quotaUsers.map((u) => (
                                    <tr key={u.email}>
                                        <td className="font-medium">{u.name}</td>
                                        <td className="text-muted">{u.email}</td>
                                        <td style={{position: 'relative'}}>
                                            <div 
                                                className={`role-badge ${u.is_admin ? "admin" : "user"} ${u.email !== user?.email ? "clickable" : ""}`}
                                                onClick={() => {
                                                    if (u.email !== user?.email) {
                                                        setOpenRoleDropdown(openRoleDropdown === u.email ? null : u.email);
                                                    }
                                                }}
                                                title={u.email !== user?.email ? "Click to change role" : ""}
                                            >
                                                {u.is_admin ? "Admin" : "User"}
                                                {u.email !== user?.email && <span className="dropdown-arrow ml-2">▾</span>}
                                            </div>
                                            
                                            {openRoleDropdown === u.email && (
                                                <div className="role-dropdown">
                                                    <div 
                                                        className={`role-dropdown-item ${u.is_admin ? "active" : ""}`} 
                                                        onClick={() => { handleSetAdmin(u.email, true); setOpenRoleDropdown(null); }}
                                                    >
                                                        Admin
                                                    </div>
                                                    <div 
                                                        className={`role-dropdown-item ${!u.is_admin ? "active" : ""}`} 
                                                        onClick={() => { handleSetAdmin(u.email, false); setOpenRoleDropdown(null); }}
                                                    >
                                                        User
                                                    </div>
                                                </div>
                                            )}
                                        </td>
                                        <td>
                                            {editingEmail === u.email ? (
                                                <div className="edit-limit-cell">
                                                    <input 
                                                        type="number" 
                                                        className="limit-input"
                                                        value={editLimit} 
                                                        onChange={(e) => setEditLimit(e.target.value)}
                                                    />
                                                    <button className="icon-btn save" onClick={() => handleSaveLimit(u.email, u.name)}>✓</button>
                                                    <button className="icon-btn cancel" onClick={() => setEditingEmail(null)}>✕</button>
                                                </div>
                                            ) : (
                                                <div className="display-limit-cell">
                                                    {u.daily_limit.toLocaleString()}
                                                    <button className="icon-btn edit ml-2" onClick={() => { setEditingEmail(u.email); setEditLimit(u.daily_limit.toString()); }}>✎</button>
                                                </div>
                                            )}
                                        </td>
                                        <td>{u.used_today.toLocaleString()}</td>
                                        <td>
                                            <div className="mini-quota-track">
                                                <div 
                                                    className={`mini-quota-fill ${u.remaining / u.daily_limit < 0.2 ? 'danger' : ''}`}
                                                    style={{ width: `${Math.min(100, (u.used_today / u.daily_limit) * 100)}%` }}
                                                />
                                            </div>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                                {!u.is_admin && (
                                                    <button className="text-btn danger" onClick={() => handleRemoveAccess(u.email)}>Remove Access</button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* ─── Lark Organization Sync Panel ─── */}
                <div className="admin-panel full-width org-panel">
                    <div className="panel-header">
                        <h2>Discover Lark Organization Users</h2>
                        <div className="header-actions">
                            <input 
                                type="text"
                                className="search-input"
                                placeholder="Search name or email..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                            <button className="panel-btn primary" onClick={handleSyncOrg} disabled={orgLoading}>
                                {orgLoading ? "Syncing from Lark..." : "Sync Full Directory"}
                            </button>
                        </div>
                    </div>
                    
                    {orgUsers.length === 0 ? (
                        <div className="empty-org-state">
                            <p>Click "Sync Full Directory" to fetch all users from Lark via the Contact API.</p>
                            <p className="text-sm text-muted">This will fetch the entire department tree.</p>
                        </div>
                    ) : (
                        <div className="table-container org-table">
                            <table className="admin-table">
                                <thead>
                                    <tr>
                                        <th style={{width: '60px'}}>Avatar</th>
                                        <th>Name</th>
                                        <th>Email</th>
                                        <th>Department ID</th>
                                        <th>Status</th>
                                        <th style={{textAlign: 'right'}}>Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredOrgUsers.map((u) => {
                                        const isRegistered = quotaUsers.some(qu => qu.email.toLowerCase() === u.email.toLowerCase());
                                        return (
                                            <tr key={u.email} className={isRegistered ? "row-registered" : ""}>
                                                <td>
                                                    {u.avatar_url ? (
                                                        <img src={u.avatar_url} alt="" className="table-avatar" />
                                                    ) : <div className="table-avatar-placeholder" />}
                                                </td>
                                                <td className="font-medium">{u.name}</td>
                                                <td className="text-muted">{u.email}</td>
                                                <td className="text-sm">{u.department}</td>
                                                <td>
                                                    {isRegistered ? 
                                                        <span className="status-badge yes">Has Access</span> : 
                                                        <span className="status-badge no">No Access</span>
                                                    }
                                                </td>
                                                <td style={{textAlign: 'right'}}>
                                                    {!isRegistered && (
                                                        <button className="grant-btn" onClick={() => handleGrantAccess(u)}>
                                                            Grant +
                                                        </button>
                                                    )}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    {filteredOrgUsers.length === 0 && (
                                        <tr><td colSpan="6" className="empty-table">No matching users found</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* ─── Datamart Access Control Panel ─── */}
                <div className="admin-panel full-width">
                    <div className="panel-header">
                        <h2>Datamart Access Control</h2>
                        <button className="panel-btn primary" onClick={handleSyncDatamarts} disabled={datamartsLoading}>
                            {datamartsLoading ? "Syncing..." : "Sync from BigQuery"}
                        </button>
                    </div>
                    {datamarts.length === 0 ? (
                         <div className="empty-org-state">
                             <p>No datamarts synced yet. Click "Sync from BigQuery" to fetch all tables.</p>
                         </div>
                    ) : (
                        <div className="table-container">
                            <table className="admin-table">
                                <thead>
                                    <tr>
                                        <th>Dataset</th>
                                        <th>Table Name</th>
                                        <th>User Access (Multiselect)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {datamarts.map((dm) => (
                                        <tr key={`${dm.dataset}.${dm.table}`}>
                                            <td className="font-medium">{dm.dataset}</td>
                                            <td>{dm.table}</td>
                                            <td>
                                                <select 
                                                    multiple
                                                    className="datamart-select"
                                                    value={dm.allowed_users}
                                                    onChange={(e) => handleUpdateDatamartAccess(dm.dataset, dm.table, e.target)}
                                                >
                                                    {quotaUsers.map(u => (
                                                        <option key={u.email} value={u.email}>{u.name} ({u.email}) {!u.is_admin ? "" : "[Admin]"}</option>
                                                    ))}
                                                </select>
                                                <div className="text-sm text-muted mt-1">Hint: Use Ctrl/Cmd+Click to select multiple. Admins always have access.</div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>
        </div>
    </div>
</div>
    );
}
