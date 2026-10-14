// Couche d'accès à l'API back-end.
async function request(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `Erreur HTTP ${res.status}`);
  return body;
}

export const api = {
  overview: () => request('/api/overview'),
  ranking: (index) => request(`/api/rankings/${index}`),
  player: (id) => request(`/api/players/${encodeURIComponent(id)}`),
  wiki: (id) => request(`/api/wiki/${encodeURIComponent(id)}`),
  saveWiki: (id, text) => request(`/api/wiki/${encodeURIComponent(id)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }),
  }),
  sync: (refresh = false) => request('/api/sync', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh }),
  }),
};
