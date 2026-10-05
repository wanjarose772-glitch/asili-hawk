const BASE = import.meta.env.VITE_API_URL || "";

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export default {
  hawk: (limit = 25) => get(`/api/hawk?limit=${limit}`),
  stats: () => get("/api/stats"),
  health: () => get("/api/health"),
  focus: (limit = 25) => get(`/api/focus?limit=${limit}`),
  breakout: (limit = 20) => get(`/api/breakout?limit=${limit}`),
  lottery: (limit = 20) => get(`/api/lottery?limit=${limit}`),
  journal: (limit = 50) => get(`/api/journal?limit=${limit}`),
  journalStats: () => get("/api/journal/stats"),
  logJournal: (body) => post("/api/journal", body),
  logOutcome: (id, body) => post(`/api/journal/${id}/outcome`, body),
};
