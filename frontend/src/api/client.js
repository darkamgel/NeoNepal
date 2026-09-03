const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    // Surface the API's own detail message (e.g. rate-limit "try again in
    // ~Ns") rather than just the status code, when the body provides one.
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `${options?.method || "GET"} ${path} failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  listWatersheds: () => request("/watersheds"),
  getWatershed: (id) => request(`/watersheds/${id}`),
  getRiskHistory: (id, limit = 200) => request(`/watersheds/${id}/risk-history?limit=${limit}`),
  getObservations: (id) => request(`/watersheds/${id}/observations`),
  getSensorReadings: (id, limit = 200) =>
    request(`/watersheds/${id}/sensor-readings?limit=${limit}`),
  postSensorReading: (id, reading) =>
    request(`/watersheds/${id}/sensor-readings`, {
      method: "POST",
      body: JSON.stringify(reading),
    }),
  listAlerts: () => request("/alerts"),
  triggerCycle: () => request("/cycle/run", { method: "POST" }),
  searchGlaciers: (q, limit = 20) =>
    request(`/glaciers/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  listGlaciers: ({ sort = "name", limit = 50, offset = 0 } = {}) =>
    request(`/glaciers?sort=${sort}&limit=${limit}&offset=${offset}`),
  getGlacier: (id) => request(`/glaciers/${id}`),
  getGlacierStats: () => request("/glaciers/stats"),
  analyzeGlacier: (id) => request(`/glaciers/${id}/analyze`, { method: "POST" }),
  getGlacierRiskHistory: (id) => request(`/glaciers/${id}/risk-history`),
};
