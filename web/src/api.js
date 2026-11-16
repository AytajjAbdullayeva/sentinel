// Thin API client. Base URL is /api in dev (Vite proxy) or VITE_API_BASE in a build.
const BASE = import.meta.env.VITE_API_BASE || "/api";

export function getToken() {
  return sessionStorage.getItem("sentinel_token") || "";
}
export function setSession(token, org, role) {
  sessionStorage.setItem("sentinel_token", token);
  sessionStorage.setItem("sentinel_org", org);
  sessionStorage.setItem("sentinel_role", role);
}
export function clearSession() {
  sessionStorage.removeItem("sentinel_token");
  sessionStorage.removeItem("sentinel_org");
  sessionStorage.removeItem("sentinel_role");
}
export function session() {
  return { token: getToken(), org: sessionStorage.getItem("sentinel_org"), role: sessionStorage.getItem("sentinel_role") };
}

async function req(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const t = getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${BASE}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, data?.detail || res.statusText, data);
  return data;
}

export class ApiError extends Error {
  constructor(status, message, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export const api = {
  login: (username, password) => req("POST", "/auth/login", { username, password }),
  me: () => req("GET", "/me"),
  listScans: () => req("GET", "/scans"),
  createScan: (name, source) => req("POST", "/scans", { name, source }),
  getScan: (id) => req("GET", `/scans/${id}`),
  findings: (id) => req("GET", `/scans/${id}/findings`),
  graph: (id) => req("GET", `/scans/${id}/graph`),
  narratives: (id) => req("GET", `/scans/${id}/narratives`),
  score: (id) => req("GET", `/scans/${id}/score`),
  diff: (baseline_scan_id, name, source, threshold) =>
    req("POST", "/diff", { baseline_scan_id, name, source, threshold }),
  simulate: (scenario, patched, eth_price_usd) =>
    req("POST", "/simulate", { scenario, patched, eth_price_usd }),
  monitorDemo: () => req("POST", "/monitor/demo"),
  // repositories (GitHub-style)
  listRepos: () => req("GET", "/repos"),
  createRepo: (name, github_url) => req("POST", "/repos", { name, github_url }),
  getRepo: (id) => req("GET", `/repos/${id}`),
  getRepoFile: (id, path) => req("GET", `/repos/${id}/file?path=${encodeURIComponent(path)}`),
  addRepoFile: (id, path, content) => req("POST", `/repos/${id}/files`, { path, content }),
  analyzeRepoFile: (id, path) => req("POST", `/repos/${id}/analyze`, { path }),
};
