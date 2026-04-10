/**
 * API service for communicating with the backend.
 * Uses Authorization Bearer token from localStorage for auth.
 */

import { getAuthToken } from "../contexts/AuthContext";

const API_BASE = import.meta.env.VITE_API_URL || "https://prompt2viz-backend-767416511940.asia-southeast2.run.app";

/**
 * Build headers with auth token.
 */
function authHeaders(extra = {}) {
    const headers = { ...extra };
    const token = getAuthToken();
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
}

/**
 * Handle response — if 401, reload to trigger login page.
 */
async function handleResponse(response) {
    if (response.status === 401) {
        localStorage.removeItem("lark_session_token");
        window.location.reload();
        throw new Error("Session expired. Please login again.");
    }
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `Request failed with status ${response.status}`);
    }
    return response.json();
}

/**
 * Call the /api/visualize endpoint.
 * @param {string} prompt - The user's question
 * @param {Object} options - { tableName, dataset } or { data }
 * @returns {Promise<Object>} The visualization response
 */
export async function generateVisualization(prompt, { data, tableName, dataset }) {
    const body = { prompt };
    if (tableName) {
        body.table_name = tableName;
        body.dataset = dataset;
    } else {
        body.data = data;
    }

    const response = await fetch(`${API_BASE}/api/visualize`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(body),
    });

    return handleResponse(response);
}

/**
 * Fetch available BigQuery tables for a given dataset (company).
 * @param {string} dataset - The dataset/company name
 * @returns {Promise<Object>} { dataset: string, tables: Array<{name, row_count}> }
 */
export async function fetchTables(dataset) {
    const response = await fetch(`${API_BASE}/api/tables?dataset=${encodeURIComponent(dataset)}`, {
        headers: authHeaders(),
    });
    return handleResponse(response);
}

/**
 * Health check
 */
export async function healthCheck() {
    const response = await fetch(`${API_BASE}/api/health`);
    return response.json();
}

/**
 * Fetch the current user's token quota info.
 * @returns {Promise<Object>} { registered, email, daily_limit, used_today, remaining, date, is_admin }
 */
export async function fetchQuota() {
    const response = await fetch(`${API_BASE}/api/quota`, {
        headers: authHeaders(),
    });
    return handleResponse(response);
}

// ── Admin API ────────────────────────────────────

/**
 * Fetch all users from the Lark organization.
 * @returns {Promise<Object>} { users: Array<OrgUser> }
 */
export async function fetchOrgUsers() {
    const response = await fetch(`${API_BASE}/api/admin/org-users`, {
        headers: authHeaders(),
    });
    return handleResponse(response);
}

/**
 * Fetch all registered users with quota settings.
 * @returns {Promise<Object>} { users: Array<QuotaSettingEntry> }
 */
export async function fetchQuotaSettings() {
    const response = await fetch(`${API_BASE}/api/admin/quota-settings`, {
        headers: authHeaders(),
    });
    return handleResponse(response);
}

/**
 * Add or update a user's quota settings.
 * @param {string} email
 * @param {string} name
 * @param {number} dailyLimit
 */
export async function updateUserQuota(email, name, dailyLimit) {
    const response = await fetch(`${API_BASE}/api/admin/update-user`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ email, name, daily_limit: dailyLimit }),
    });
    return handleResponse(response);
}

/**
 * Remove a user's access.
 * @param {string} email
 */
export async function removeUserQuota(email) {
    const response = await fetch(`${API_BASE}/api/admin/remove-user`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ email }),
    });
    return handleResponse(response);
}

/**
 * Change a user's admin role.
 * @param {string} email
 * @param {boolean} isAdmin
 */
export async function setAdminRole(email, isAdmin) {
    const response = await fetch(`${API_BASE}/api/admin/set-admin`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ email, is_admin: isAdmin }),
    });
    return handleResponse(response);
}

