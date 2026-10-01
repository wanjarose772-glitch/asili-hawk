const BASE = import.meta.env.VITE_API_URL || "";

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export default {
  hawk: (limit = 25) => get(`/api/hawk?limit=${limit}`),
  stats: () => get("/api/stats"),
  health: () => get("/api/health"),
};
