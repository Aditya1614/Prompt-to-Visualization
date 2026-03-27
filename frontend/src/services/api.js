/**
 * API service for communicating with the backend.
 */

const API_BASE = import.meta.env.VITE_API_URL || "https://prompt2viz-backend-767416511940.asia-southeast2.run.app";

/**
 * Handle response — if 401, redirect to login.
 */
async function handleResponse(response) {
    if (response.status === 401) {
        // Session expired or not authenticated — reload to trigger login page
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
        headers: { "Content-Type": "application/json" },
        credentials: "include",
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
        credentials: "include",
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
