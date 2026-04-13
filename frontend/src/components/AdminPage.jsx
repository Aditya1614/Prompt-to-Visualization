import { useState, useEffect, useMemo } from "react";
import { useAuth } from "../contexts/AuthContext";
import { Link, Navigate } from "react-router-dom";
import { 
    fetchOrgHierarchy, fetchQuotaSettings, updateUserQuota, removeUserQuota, fetchQuota, setAdminRole,
    fetchAdminDatamarts, syncAdminDatamarts, updateDatamartAccess
} from "../services/api";
import "./AdminPage.css";

// --- Icons ---
const ChevronDown = ({ className }) => (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>
);

const UserPlus = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="16" y1="11" x2="22" y2="11"/></svg>
);

const RefreshIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/></svg>
);

// --- Sub-Components ---

const UserItem = ({ user, type, onGrant, onRemove, onSetAdmin, onEditLimit, isSelf }) => {
    const isRegistered = type === 'registered';
    const [isEditing, setIsEditing] = useState(false);
    const [tempLimit, setTempLimit] = useState(user.daily_limit || 100000);
    const [showRoleMenu, setShowRoleMenu] = useState(false);

    const progress = user.daily_limit ? Math.min(100, (user.used_today / user.daily_limit) * 100) : 0;

    return (
        <div className="user-card">
            <div className="user-main-info">
                {user.avatar_url ? (
                    <img src={user.avatar_url} alt="" className="user-avatar" />
                ) : (
                    <div className="user-avatar" style={{ background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontWeight: 600 }}>
                        {user.name.charAt(0)}
                    </div>
                )}
                <div className="user-details">
                    <h3>{user.name}</h3>
                    <p>{user.email}</p>
                </div>
                <div className="role-dropdown-container">
                    <span 
                        className={`role-badge ${user.is_admin ? 'admin' : isRegistered ? 'user' : 'no-access'} ${isRegistered && !isSelf ? 'clickable' : ''}`}
                        onClick={() => isRegistered && !isSelf && setShowRoleMenu(!showRoleMenu)}
                    >
                        {user.is_admin ? 'ADMIN' : isRegistered ? 'USER' : 'NO ACCESS'}
                    </span>
                    {showRoleMenu && (
                        <div className="role-dropdown">
                            <div className="role-dropdown-item" onClick={() => { onSetAdmin(user.email, true); setShowRoleMenu(false); }}>Admin</div>
                            <div className="role-dropdown-item" onClick={() => { onSetAdmin(user.email, false); setShowRoleMenu(false); }}>User</div>
                        </div>
                    )}
                </div>
            </div>

            {isRegistered && (
                <div className="user-meta">
                    <div className="quota-section">
                        <div className="quota-labels">
                            <div className="limit-edit-row">
                                {isEditing ? (
                                    <>
                                        <input 
                                            type="number" 
                                            className="limit-inline-input" 
                                            value={tempLimit} 
                                            onChange={(e) => setTempLimit(e.target.value)} 
                                            autoFocus
                                        />
                                        <button className="edit-trigger" onClick={() => { onEditLimit(user.email, user.name, tempLimit); setIsEditing(false); }}>Save</button>
                                        <button className="edit-trigger" onClick={() => setIsEditing(false)}>Cancel</button>
                                    </>
                                ) : (
                                    <>
                                        <span className="quota-limit">{(user.daily_limit || 0).toLocaleString()}</span>
                                        <span className="quota-usage" style={{ marginLeft: '4px' }}>Daily Limit</span>
                                        <button className="edit-trigger" onClick={() => setIsEditing(true)}>Edit</button>
                                    </>
                                )}
                            </div>
                            <span className="quota-usage">{(user.used_today || 0).toLocaleString()} / {(user.daily_limit || 0).toLocaleString()}</span>
                        </div>
                        <div className="progress-track">
                            <div className={`progress-fill ${progress > 85 ? 'danger' : ''}`} style={{ width: `${progress}%` }} />
                        </div>
                    </div>
                    {!isSelf && <button className="btn-remove" onClick={() => onRemove(user.email)}>Remove Access</button>}
                </div>
            )}

            {!isRegistered && (
                <button className="btn-grant" onClick={() => onGrant(user)}>
                    <UserPlus /> Grant +
                </button>
            )}
        </div>
    );
};

export default function AdminPage() {
    const { user, loading: authLoading } = useAuth();
    const [isAdmin, setIsAdmin] = useState(false);
    const [adminLoading, setAdminLoading] = useState(true);

    const [orgHierarchy, setOrgHierarchy] = useState([]);
    const [quotaUsers, setQuotaUsers] = useState([]);
    
    const [orgLoading, setOrgLoading] = useState(false);
    const [quotaLoading, setQuotaLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");

    // Accordion states
    const [regOpen, setRegOpen] = useState(true);
    const [discOpen, setDiscOpen] = useState(true);
    const [openDepts, setOpenDepts] = useState({});

    // Datamart state
    const [datamarts, setDatamarts] = useState([]);
    const [datamartsLoading, setDatamartsLoading] = useState(false);

    // Initial load
    useEffect(() => {
        if (!user) return;
        async function checkAdmin() {
            try {
                const q = await fetchQuota();
                setIsAdmin(q.is_admin === true);
            } catch (err) { console.error(err); } 
            finally { setAdminLoading(false); }
        }
        checkAdmin();
    }, [user]);

    useEffect(() => {
        if (isAdmin) {
            loadQuotaSettings();
            loadDatamarts();
        }
    }, [isAdmin]);

    const loadQuotaSettings = async () => {
        setQuotaLoading(true);
        try {
            const data = await fetchQuotaSettings();
            setQuotaUsers(data.users || []);
        } catch (err) { console.error(err); } 
        finally { setQuotaLoading(false); }
    };

    const loadDatamarts = async () => {
        setDatamartsLoading(true);
        try {
            const data = await fetchAdminDatamarts();
            setDatamarts(data.datamarts || []);
        } catch (err) { console.error(err); } 
        finally { setDatamartsLoading(false); }
    };

    const handleSyncOrg = async () => {
        setOrgLoading(true);
        try {
            const data = await fetchOrgHierarchy();
            setOrgHierarchy(data.departments || []);
            // Open first department by default
            if (data.departments?.length > 0) {
                setOpenDepts(prev => ({ ...prev, [data.departments[0].department_id]: true }));
            }
        } catch (err) { alert(`Sync failed: ${err.message}`); } 
        finally { setOrgLoading(false); }
    };

    const handleGrantAccess = async (orgUser) => {
        try {
            await updateUserQuota(orgUser.email, orgUser.name, 100000, orgUser.department);
            loadQuotaSettings();
        } catch (err) { alert("Grant Access failed"); }
    };

    const handleGrantAll = async (dept) => {
        if (!confirm(`Grant 100k quota to all users in ${dept.department_name}?`)) return;
        setOrgLoading(true);
        let count = 0;
        try {
            for (const u of dept.users) {
                const isAlready = quotaUsers.some(qu => qu.email.toLowerCase() === u.email.toLowerCase());
                if (!isAlready) {
                    await updateUserQuota(u.email, u.name, 100000, dept.department_name);
                    count++;
                }
            }
            alert(`Granted access to ${count} new users.`);
            loadQuotaSettings();
        } catch (err) { alert("Grant All failed mid-process"); }
        finally { setOrgLoading(false); }
    };

    const handleRemoveAccess = async (email) => {
        if (!confirm(`Remove access for ${email}?`)) return;
        try {
            await removeUserQuota(email);
            loadQuotaSettings();
        } catch (err) { alert("Remove failed"); }
    };

    const handleSetAdmin = async (email, status) => {
        try {
            await setAdminRole(email, status);
            loadQuotaSettings();
        } catch (err) { alert("Role update failed"); }
    };

    const handleEditLimit = async (email, name, newLimit) => {
        try {
            await updateUserQuota(email, name, parseInt(newLimit), ""); // department not needed for simple limit update
            loadQuotaSettings();
        } catch (err) { alert("Limit update failed"); }
    };

    // Derived Data
    const stats = useMemo(() => ({
        total: quotaUsers.length,
        active: quotaUsers.filter(u => u.used_today > 0).length,
        tokens: quotaUsers.reduce((s, u) => s + u.used_today, 0)
    }), [quotaUsers]);

    const registeredByDept = useMemo(() => {
        const groups = {};
        quotaUsers.forEach(u => {
            const dept = u.department || "Other";
            if (!groups[dept]) groups[dept] = [];
            groups[dept].push(u);
        });
        return groups;
    }, [quotaUsers]);

    const filteredHierarchy = useMemo(() => {
        if (!searchQuery) return orgHierarchy;
        const q = searchQuery.toLowerCase();
        return orgHierarchy.map(dept => ({
            ...dept,
            users: dept.users.filter(u => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q))
        })).filter(dept => dept.users.length > 0);
    }, [orgHierarchy, searchQuery]);

    if (authLoading || adminLoading) return <div className="page-bg"><div className="empty-state">Loading Dashboard...</div></div>;
    if (!user || !isAdmin) return <Navigate to="/" />;

    return (
        <div className="admin-page">
            <header className="admin-header">
                <h1 className="admin-title">Organization Access Control Dashboard</h1>
                <p className="admin-subtitle">Manage departmental quotas and user access</p>
            </header>

            <div className="admin-stats">
                <div className="stat-card">
                    <div className="stat-label">Registered Users</div>
                    <div className="stat-value">{stats.total}</div>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Active Today</div>
                    <div className="stat-value">{stats.active}</div>
                </div>
                <div className="stat-card stat-primary">
                    <div className="stat-label">Total Tokens Used (Today)</div>
                    <div className="stat-value">{stats.tokens.toLocaleString()}</div>
                </div>
            </div>

            <div className="admin-grid">
                {/* --- REGISTERED USERS --- */}
                <div className="admin-panel">
                    <div className="panel-header" onClick={() => setRegOpen(!regOpen)}>
                        <h2>
                            <ChevronDown className={`chevron-icon ${regOpen ? 'open' : ''}`} />
                            Registered Users ({stats.total})
                        </h2>
                        <button className="panel-btn" onClick={(e) => { e.stopPropagation(); loadQuotaSettings(); }}>
                            <RefreshIcon />
                        </button>
                    </div>
                    {regOpen && (
                        <div className="accordion-content">
                            {Object.entries(registeredByDept).length === 0 ? (
                                <div className="empty-state">No users registered.</div>
                            ) : Object.entries(registeredByDept).map(([deptName, users]) => (
                                <div key={deptName} className="dept-group">
                                    <div className="dept-header" onClick={() => setOpenDepts(p => ({ ...p, [deptName]: !p[deptName] }))}>
                                        <span>{deptName} ({users.length})</span>
                                        <ChevronDown className={`chevron-icon ${openDepts[deptName] ? 'open' : ''}`} />
                                    </div>
                                    {openDepts[deptName] && (
                                        <div className="dept-users">
                                            {users.map(u => (
                                                <UserItem 
                                                    key={u.email} user={u} type="registered" 
                                                    onRemove={handleRemoveAccess} onSetAdmin={handleSetAdmin} 
                                                    onEditLimit={handleEditLimit} isSelf={u.email === user.email}
                                                />
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* --- DISCOVER USERS --- */}
                <div className="admin-panel">
                    <div className="panel-header" onClick={() => setDiscOpen(!discOpen)}>
                        <h2>
                            <ChevronDown className={`chevron-icon ${discOpen ? 'open' : ''}`} />
                            Discover Lark Organization Users
                        </h2>
                    </div>
                    {discOpen && (
                        <>
                            <div className="discover-header-row">
                                <div className="search-field">
                                    <input 
                                        type="text" className="search-input" placeholder="Search name or email..." 
                                        value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                                    />
                                </div>
                                <button className="btn-primary" onClick={handleSyncOrg} disabled={orgLoading}>
                                    {orgLoading ? "Syncing..." : "Sync Full Directory"}
                                </button>
                            </div>
                            <div className="accordion-content">
                                {orgHierarchy.length === 0 ? (
                                    <div className="empty-state">Sync the directory to discover organizational users.</div>
                                ) : filteredHierarchy.map(dept => (
                                    <div key={dept.department_id} className="dept-group">
                                        <div className="dept-header" onClick={() => setOpenDepts(p => ({ ...p, [dept.department_id]: !p[dept.department_id] }))}>
                                            <span>Department: {dept.department_name} ({dept.users.length})</span>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                                <button className="btn-secondary" style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }} onClick={(e) => { e.stopPropagation(); handleGrantAll(dept); }}>Grant All +</button>
                                                <ChevronDown className={`chevron-icon ${openDepts[dept.department_id] ? 'open' : ''}`} />
                                            </div>
                                        </div>
                                        {openDepts[dept.department_id] && (
                                            <div className="dept-users">
                                                {dept.users.map(u => {
                                                    const isRegistered = quotaUsers.some(qu => qu.email.toLowerCase() === u.email.toLowerCase());
                                                    if (isRegistered) return null; // Only show unregistered in discovery
                                                    return <UserItem key={u.email} user={u} type="discovery" onGrant={handleGrantAccess} />;
                                                })}
                                                {dept.users.every(u => quotaUsers.some(qu => qu.email.toLowerCase() === u.email.toLowerCase())) && (
                                                    <div className="empty-state" style={{ padding: '1rem' }}>All users in this department have access.</div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </div>

                {/* --- DATAMART ACCESS --- */}
                <div className="admin-panel">
                    <div className="panel-header">
                        <h2>Datamart Access Control</h2>
                        <button className="btn-primary" onClick={() => syncAdminDatamarts().then(loadDatamarts)}>Sync from BQ</button>
                    </div>
                    <div style={{ padding: '1.5rem' }}>
                        {datamarts.map(dm => (
                            <div key={`${dm.dataset}.${dm.table}`} style={{ marginBottom: '1.5rem', padding: '1rem', border: '1px solid #e2e8f0', borderRadius: '0.75rem' }}>
                                <div style={{ fontWeight: 700, marginBottom: '0.5rem' }}>{dm.dataset}.{dm.table}</div>
                                <select 
                                    multiple className="datamart-select" value={dm.allowed_users}
                                    onChange={async (e) => {
                                        const values = Array.from(e.target.selectedOptions, opt => opt.value);
                                        await updateDatamartAccess(dm.dataset, dm.table, values);
                                        loadDatamarts();
                                    }}
                                >
                                    {quotaUsers.map(u => <option key={u.email} value={u.email}>{u.name} ({u.email})</option>)}
                                </select>
                                <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.5rem' }}>Hold Cmd/Ctrl to select multiple users.</p>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
            
            <footer style={{ marginTop: '3rem', textAlign: 'center', padding: '2rem', color: '#94a3b8', fontSize: '0.9rem' }}>
                &copy; 2026 Organization Access Control System
            </footer>
        </div>
    );
}
