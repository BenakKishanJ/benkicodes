// Thin fetch/SSE client for the local pipeline API. Token lives in localStorage
// only; every authed request carries X-Admin-Token (PRD 02 §8.1).
import type { EventView, LibraryItem, ModelEntry, RunItem, RunView, SettingsView } from './types';

const TOKEN_KEY = 'benki-admin-token';
const BASE_KEY = 'benki-admin-api';
export const API_DEFAULT = 'http://127.0.0.1:8787';

export const getToken = () => localStorage.getItem(TOKEN_KEY) ?? '';
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t.trim());
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);
export const getBase = () => localStorage.getItem(BASE_KEY) ?? API_DEFAULT;
export const setBase = (u: string) => localStorage.setItem(BASE_KEY, u.trim().replace(/\/+$/, ''));

export class ApiError extends Error {
  constructor(readonly status: number, readonly detail: string) {
    super(`${status} ${detail}`);
  }
}

async function res(r: Response): Promise<unknown> {
  if (r.ok) {
    if (r.status === 204) return null;
    const ct = r.headers.get('content-type') ?? '';
    return ct.includes('json') ? r.json() : r.text();
  }
  let detail = `${r.status}`;
  try {
    const body = (await r.json()) as { detail?: unknown };
    detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
  } catch { /* text error bodies */ }
  if (detail.length > 200) detail = `${detail.slice(0, 200)}…`;
  throw new ApiError(r.status, detail);
}

async function req(path: string, init: RequestInit = {}, authed = true): Promise<unknown> {
  const headers: Record<string, string> = {
    ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    ...(authed ? { 'X-Admin-Token': getToken() } : {}),
  };
  const r = await fetch(`${getBase()}${path}`, { ...init, headers });
  return res(r);
}

export const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) });

export const api = {
  health: () => req('/health', {}, false),
  settings: () => req('/settings') as Promise<SettingsView>,
  credits: () => req('/credits') as Promise<Record<string, number>>,
  models: (q = '', opts: { limit?: number; free?: boolean; structured?: boolean } = {}) => {
    const p = new URLSearchParams({ q, limit: String(opts.limit ?? 60) });
    if (opts.free) p.set('free', 'true');
    if (opts.structured) p.set('structured', 'true');
    return req(`/models?${p}`) as Promise<ModelEntry[]>;
  },
  smoke: (mid: string) => req(`/models/${mid}/smoke`, json({})),
  runs: () => req('/runs') as Promise<RunItem[]>,
  run: (id: string) => req(`/runs/${id}`) as Promise<RunView>,
  newRun: (body: unknown) => req('/runs', json(body)) as Promise<{ id: string }>,
  resume: (id: string, decision: unknown) => req(`/runs/${id}/resume`, json(decision)),
  budget: (id: string, budgetUsd: number) => req(`/runs/${id}/budget`, json({ budget_usd: budgetUsd })),
  retry: (id: string) => req(`/runs/${id}/retry`, json({})),
  del: (id: string) => req(`/runs/${id}`, { method: 'DELETE' }),
  library: () => req('/library') as Promise<LibraryItem[]>,
};

export interface StreamFrame {
  status: string;
  events: EventView[];
  spent: number;
  pending: string | null;
}

/**
 * SSE via fetch (EventSource cannot send the token header). Calls
 * onFrame per message, onTransition/hint on an event transition, onDone when
 * the run reaches a terminal state, and onError once if the stream fails
 * (caller falls back to polling). Returns a cancel function.
 */
export function streamRun(
  id: string,
  onFrame: (f: StreamFrame) => void,
  onDone: () => void,
  onError: (e: unknown) => void,
): () => void {
  const ctl = new AbortController();
  (async () => {
    let buf = '';
    const r = await fetch(`${getBase()}/runs/${id}/stream`, {
      headers: { 'X-Admin-Token': getToken() },
      signal: ctl.signal,
    });
    if (!r.ok || !r.body) throw new ApiError(r.status, `stream failed (${r.status})`);
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx: number;
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const eventName = /^event:\s*(.+)$/m.exec(chunk)?.[1] ?? 'message';
        const data = /^data:\s*(.*)$/m.exec(chunk)?.[1];
        if (eventName === 'done') { onDone(); return; }
        if (eventName === 'gone') { onDone(); return; } // run was deleted
        if (!data) continue;
        if (eventName === 'transition') continue; // the data frame already carries status
        try { onFrame(JSON.parse(data) as StreamFrame); } catch { /* partial frame */ }
      }
    }
    onDone(); // server closed without a done event (e.g. stream timeout)
  })().catch((e) => { if (!ctl.signal.aborted) onError(e); });
  return () => ctl.abort();
}

export const busy = (s: string) =>
  s === 'working' || s === 'queued' || s === 'streaming' || s === 'writing' || s === 'checking';
export const terminal = (s: string) => s === 'published' || s === 'failed' || s === 'rejected';
export const needsDecision = (s: string) => s === 'awaiting_plan' || s === 'awaiting_review';

export function statusColor(s: string): string {
  if (s === 'published') return 'var(--green)';
  if (s === 'failed' || s === 'rejected') return 'var(--red)';
  if (s === 'awaiting_plan' || s === 'awaiting_review') return 'var(--yellow)';
  if (s === 'paused_budget' || s === 'warn') return 'var(--yellow)';
  if (busy(s)) return 'var(--accent)';
  return 'var(--muted)';
}

export function fmtTs(ts?: string): string {
  if (!ts) return '—';
  try { return new Date(ts).toLocaleString(); } catch { return ts; }
}

export const usd = (n: unknown): string => `$${typeof n === 'number' ? n.toFixed(n < 1 ? 4 : 2) : '0'}`;
