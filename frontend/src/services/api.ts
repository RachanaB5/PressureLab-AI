import { suggestLocalMatches, MATCH_CATALOG } from '../data/matchCatalog';

const API_BASE = '/api';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API Error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function suggestWithFallback(q: string): Promise<{ suggestions: any[]; offline?: boolean }> {
  const validIds = new Set(MATCH_CATALOG.map(m => m.statsbomb_id));
  const filterValid = (items: any[]) =>
    items.filter(s => !s.statsbomb_id || validIds.has(s.statsbomb_id));

  try {
    const res = await fetchJSON<{ suggestions: any[] }>(`/matches/suggest?q=${encodeURIComponent(q)}`);
    return { suggestions: filterValid(res.suggestions) };
  } catch {
    return { suggestions: suggestLocalMatches(q), offline: true };
  }
}

export const matchApi = {
  suggest: suggestWithFallback,
  health: () => fetchJSON<{ status: string }>('/health'),
  getMatch: (id: number) => fetchJSON<any>(`/matches/${id}`),
  getStatus: (id: number) => fetchJSON<any>(`/matches/${id}/status`),
  importMatch: (body: { statsbomb_id?: number; match_id?: number }) =>
    fetchJSON<any>('/matches/import', { method: 'POST', body: JSON.stringify(body) }),
  getKeyEvents: (id: number) => fetchJSON<{ events: any[]; goals?: any[] }>(`/matches/${id}/key-events`),
  getMoment: (matchId: number, eventId: number) =>
    fetchJSON<any>(`/matches/${matchId}/moments/${eventId}`),
  libraryCatalog: (query: string) => fetchJSON<any>(`/library/catalog?${query}`),
  detectiveChoice: (matchId: number, eventId: number, choice: string) =>
    fetchJSON<any>(`/matches/${matchId}/moments/${eventId}/detective`, {
      method: 'POST',
      body: JSON.stringify({ choice }),
    }),
};

export const copilotApi = {
  ask: (
    question: string,
    matchId: number,
    minute: number,
    eventId?: number,
    conversationHistory?: Array<{ q: string; a: string }>,
  ) =>
    fetchJSON<any>('/explain/query', {
      method: 'POST',
      body: JSON.stringify({
        question,
        match_id: matchId,
        minute,
        event_id: eventId ?? null,
        page_context: eventId ? `Workspace event ${eventId} at ${minute}'` : `Workspace minute ${minute}'`,
        conversation_history: conversationHistory ?? [],
      }),
    }),
};
