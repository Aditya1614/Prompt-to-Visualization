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

const ArrowLeft = () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>
);

const TrashIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6"/></svg>
);

const SettingsIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
);

const CloseIcon = () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
);

const SearchIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
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

// --- Datamart Modals ---

const AddDeptModal = ({ isOpen, onClose, departments, onAdd }) => {
    const [selectedDepts, setSelectedDepts] = useState([]);
    const [search, setSearch] = useState("");

    if (!isOpen) return null;

    const filtered = departments.filter(d => d.toLowerCase().includes(search.toLowerCase()));

    const toggle = (dept) => {
        if (selectedDepts.includes(dept)) setSelectedDepts(selectedDepts.filter(d => d !== dept));
        else setSelectedDepts([...selectedDepts, dept]);
    };

    return (
        <div className="modal-overlay">
            <div className="modal-content">
                <div className="modal-header">
                    <h2>Add Department Access</h2>
                    <button className="btn-icon" onClick={onClose}><CloseIcon /></button>
                </div>
                <div className="modal-body">
                    <div className="search-field" style={{ marginBottom: '1rem' }}>
                        <input className="search-input" placeholder="Search departments..." value={search} onChange={e => setSearch(e.target.value)} />
                    </div>
                    {filtered.map(dept => (
                        <label key={dept} className="list-item-checkbox">
                            <input type="checkbox" checked={selectedDepts.includes(dept)} onChange={() => toggle(dept)} />
                            <span>{dept}</span>
                        </label>
                    ))}
                </div>
                <div className="modal-footer">
                    <button className="btn-modal-primary" onClick={() => { onAdd(selectedDepts); onClose(); }}>Add Selected Departments</button>
                    <button className="btn-modal-secondary" onClick={onClose}>Cancel</button>
                </div>
            </div>
        </div>
    );
};

const AddUserModal = ({ isOpen, onClose, orgUsers, onAdd, deptName }) => {
    const [search, setSearch] = useState("");
    if (!isOpen) return null;

    const filtered = orgUsers.filter(u => 
        (u.name?.toLowerCase().includes(search.toLowerCase()) || u.email?.toLowerCase().includes(search.toLowerCase()))
    );

    return (
        <div className="modal-overlay">
            <div className="modal-content">
                <div className="modal-header">
                    <div>
                        <h2>Add Users to {deptName}</h2>
                        <p className="text-sm text-muted">Grant access individually</p>
                    </div>
                    <button className="btn-icon" onClick={onClose}><CloseIcon /></button>
                </div>
                <div className="modal-body">
                    <div className="search-field" style={{ marginBottom: '1rem' }}>
                        <input className="search-input" placeholder="Search organization users..." value={search} onChange={e => setSearch(e.target.value)} />
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {filtered.map(u => (
                            <div key={u.email} className="user-access-item" style={{ padding: '0.5rem 0' }}>
                                <div className="user-access-info">
                                    <img src={u.avatar_url || ""} alt="" className="user-access-avatar" style={{ background: '#f1f5f9' }} />
                                    <div className="user-access-details">
                                        <h5>{u.name}</h5>
                                        <p>{u.email}</p>
                                    </div>
                                </div>
                                <button className="btn-grant" onClick={() => onAdd(u.email)}>Grant Access +</button>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="modal-footer">
                    <button className="btn-modal-primary" onClick={onClose}>Done</button>
                </div>
            </div>
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
    const [dmSearchQuery, setDmSearchQuery] = useState("");

    // Accordion states
    const [regOpen, setRegOpen] = useState(true);
    const [discOpen, setDiscOpen] = useState(true);
    const [openDepts, setOpenDepts] = useState({});
    const [openDmDepts, setOpenDmDepts] = useState({});

    // Datamart state
    const [datamarts, setDatamarts] = useState([]);
    const [datamartsLoading, setDatamartsLoading] = useState(false);
    
    // Modal states
    const [showDeptModal, setShowDeptModal] = useState(false);
    const [showUserModal, setShowUserModal] = useState(false);
    const [activeDm, setActiveDm] = useState(null); // { dataset, table, allowed_users }
    const [activeDept, setActiveDept] = useState(null); // string

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

    // --- Datamart Logic ---

    const handleBatchGrantDept = async (depts) => {
        if (!activeDm) return;
        const currentEmails = [...activeDm.allowed_users];
        
        depts.forEach(deptName => {
            const emailsInDept = quotaUsers
                .filter(u => u.department === deptName)
                .map(u => u.email.toLowerCase());
            
            emailsInDept.forEach(email => {
                if (!currentEmails.includes(email)) {
                    currentEmails.push(email);
                }
            });
        });

        try {
            await updateDatamartAccess(activeDm.dataset, activeDm.table, currentEmails);
            loadDatamarts();
        } catch (err) { alert("Batch grant failed"); }
    };

    const handleRemoveUserFromDm = async (dm, email) => {
        const emails = dm.allowed_users.filter(e => e.toLowerCase() !== email.toLowerCase());
        try {
            await updateDatamartAccess(dm.dataset, dm.table, emails);
            loadDatamarts();
        } catch (err) { alert("Remove user failed"); }
    };

    const handleRemoveDeptFromDm = async (dm, deptName) => {
        if (!confirm(`Remove all access for ${deptName} in ${dm.dataset}.${dm.table}?`)) return;
        const deptEmails = new Set(quotaUsers.filter(u => u.department === deptName).map(u => u.email.toLowerCase()));
        const emails = dm.allowed_users.filter(e => !deptEmails.has(e.toLowerCase()));
        try {
            await updateDatamartAccess(dm.dataset, dm.table, emails);
            loadDatamarts();
        } catch (err) { alert("Remove department failed"); }
    };

    const handleAddSingleUserToDm = async (email) => {
        if (!activeDm) return;
        const currentEmails = [...activeDm.allowed_users];
        if (!currentEmails.includes(email.toLowerCase())) {
            currentEmails.push(email.toLowerCase());
        }
        try {
            await updateDatamartAccess(activeDm.dataset, activeDm.table, currentEmails);
            loadDatamarts();
        } catch (err) { alert("Grant user failed"); }
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

    const availableDepts = useMemo(() => {
        const depts = new Set(quotaUsers.map(u => u.department || "Other"));
        return Array.from(depts).sort();
    }, [quotaUsers]);

    const filteredHierarchy = useMemo(() => {
        if (!searchQuery) return orgHierarchy;
        const q = searchQuery.toLowerCase();
        return orgHierarchy.map(dept => ({
            ...dept,
            users: dept.users.filter(u => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q))
        })).filter(dept => dept.users.length > 0);
    }, [orgHierarchy, searchQuery]);

    const groupedDatamarts = useMemo(() => {
        const q = dmSearchQuery.toLowerCase();
        
        return datamarts.map(dm => {
            const dmFullName = `${dm.dataset}.${dm.table}`.toLowerCase();
            const allowedGroups = {};
            
            dm.allowed_users.forEach(email => {
                const userObj = quotaUsers.find(qu => qu.email.toLowerCase() === email.toLowerCase());
                const dept = userObj?.department || "Other";
                if (!allowedGroups[dept]) allowedGroups[dept] = [];
                allowedGroups[dept].push({
                    email,
                    name: userObj?.name || "Unknown",
                    avatar_url: userObj?.avatar_url || "" // need to pass avatar if possible, or fetch it
                });
            });

            // Filter departments by search
            const deptsMatch = Object.keys(allowedGroups).some(d => d.toLowerCase().includes(q));
            const nameMatch = dmFullName.includes(q);

            if (nameMatch || deptsMatch) {
                return { ...dm, groups: allowedGroups };
            }
            return null;
        }).filter(Boolean);
    }, [datamarts, quotaUsers, dmSearchQuery]);

    // Flatten org users for AddUser modal
    const flatOrgUsers = useMemo(() => {
        const users = [];
        orgHierarchy.forEach(dept => {
            dept.users.forEach(u => {
                if (!users.some(existing => existing.email === u.email)) {
                    users.push(u);
                }
            });
        });
        return users;
    }, [orgHierarchy]);

    if (authLoading || adminLoading) return <div className="page-bg"><div className="empty-state">Loading Dashboard...</div></div>;
    if (!user || !isAdmin) return <Navigate to="/" />;

    return (
        <div className="admin-page">
            <header className="admin-header">
                <Link to="/" className="back-link">
                    <ArrowLeft />
                    Back to Visualization
                </Link>
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center', marginTop: '1rem' }}>
                    <div>
                        <h1 className="admin-title">Organization Access Control Dashboard</h1>
                        <p className="admin-subtitle">Manage departmental quotas and user access</p>
                    </div>
                </div>
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
                <div style={{ marginTop: '2rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '1.5rem' }}>
                        <div>
                            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, margin: 0 }}>Admin Datamart Access Control</h2>
                        </div>
                        <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }} onClick={() => syncAdminDatamarts().then(loadDatamarts)}>
                            <RefreshIcon /> Sync
                        </button>
                    </div>

                    <div className="search-field" style={{ marginBottom: '2rem' }}>
                        <div style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }}>
                            <SearchIcon />
                        </div>
                        <input 
                            className="search-input" style={{ paddingLeft: '3rem' }} 
                            placeholder="Search datasets or departments" value={dmSearchQuery} onChange={e => setDmSearchQuery(e.target.value)} 
                        />
                    </div>

                    {groupedDatamarts.map(dm => (
                        <div key={`${dm.dataset}.${dm.table}`} className="dm-card">
                            <div className="dm-card-header">
                                <h3 className="dm-card-title">{dm.dataset}.{dm.table}</h3>
                                <div className="dm-card-actions">
                                    <button className="btn-add-inline" onClick={() => { setActiveDm(dm); setShowDeptModal(true); }}>Add Department +</button>
                                </div>
                            </div>
                            <div className="dept-access-section">
                                {Object.entries(dm.groups).map(([deptName, users]) => {
                                    const dmDeptKey = `${dm.dataset}.${dm.table}.${deptName}`;
                                    const isOpen = openDmDepts[dmDeptKey];
                                    return (
                                        <div key={deptName} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                            <div className="dept-access-header" onClick={() => setOpenDmDepts(prev => ({ ...prev, [dmDeptKey]: !prev[dmDeptKey] }))}>
                                                <h4>
                                                    <ChevronDown className={`chevron-icon ${isOpen ? 'open' : ''}`} />
                                                    {deptName} ({users.length} users)
                                                </h4>
                                                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                                                    <button className="btn-add-dept btn-secondary" style={{ padding: '0.25rem 0.5rem' }} onClick={(e) => { e.stopPropagation(); setActiveDm(dm); setActiveDept(deptName); setShowUserModal(true); }}>
                                                        Add User +
                                                    </button>
                                                </div>
                                            </div>
                                            {isOpen && (
                                                <div className="user-access-list">
                                                    {users.map(u => (
                                                        <div key={u.email} className="user-access-item">
                                                            <div className="user-access-info">
                                                                <div className="user-access-avatar" style={{ background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8rem', fontWeight: 600 }}>
                                                                    {u.avatar_url ? <img src={u.avatar_url} alt="" className="user-access-avatar" /> : u.name?.charAt(0)}
                                                                </div>
                                                                <div className="user-access-details">
                                                                    <h5>{u.name}</h5>
                                                                    <p>{u.email}</p>
                                                                </div>
                                                            </div>
                                                            <button className="btn-icon" onClick={() => handleRemoveUserFromDm(dm, u.email)}>
                                                                <CloseIcon />
                                                            </button>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                                {Object.keys(dm.groups).length === 0 && <div className="empty-state" style={{ padding: '1.5rem' }}>No departments assigned yet.</div>}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <AddDeptModal 
                isOpen={showDeptModal} onClose={() => setShowDeptModal(false)}
                departments={availableDepts} onAdd={handleBatchGrantDept}
            />

            <AddUserModal 
                isOpen={showUserModal} onClose={() => setShowUserModal(false)}
                deptName={activeDept} orgUsers={flatOrgUsers} onAdd={handleAddSingleUserToDm}
            />
            
            <footer style={{ marginTop: '3rem', textAlign: 'center', padding: '2rem', color: '#94a3b8', fontSize: '0.9rem' }}>
                &copy; 2026 Organization Access Control System
            </footer>
        </div>
    );
}
