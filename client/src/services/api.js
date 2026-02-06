/**
 * SailCast API Client
 * Fetches forecast data from the FastAPI backend.
 * In development, Vite proxies /api requests to localhost:8000.
 */

const API_BASE = "/api/forecast";

async function fetchJSON(endpoint) {
  const response = await fetch(`${API_BASE}${endpoint}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch all forecast data in parallel.
 * Returns { hourly, sevenDay, alerts, summary }
 */
export async function fetchForecastData() {
  const [hourly, sevenDay, alerts, summary] = await Promise.allSettled([
    fetchJSON("/hourly"),
    fetchJSON("/7day"),
    fetchJSON("/alerts"),
    fetchJSON("/summary"),
  ]);

  return {
    hourly: hourly.status === "fulfilled" ? hourly.value : null,
    sevenDay: sevenDay.status === "fulfilled" ? sevenDay.value : null,
    alerts: alerts.status === "fulfilled" ? alerts.value : null,
    summary: summary.status === "fulfilled" ? summary.value : null,
  };
}

/**
 * Fetch health check status.
 */
export async function fetchHealthCheck() {
  return fetchJSON("/health");
}
