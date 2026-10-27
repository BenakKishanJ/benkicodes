// Admin shell (PRD 02 §8.3): connect screen, decision strip, nav, and the
// Runs / Settings / Library screens. One React island at /admin/ (dev-only).
import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, API_DEFAULT, busy, clearToken, api, fmtTs, getBase, getToken, needsDecision, setBase, setToken, usd } from './api';
import { Chip, ErrBox, Field, inputCls } from './ui';
import BlogReview from './blog/BlogReview';
import Library from './library/Library';
import NewBlogForm from './runs/NewBlogForm';
import RunList from './runs/RunList';
import Settings from './settings/Settings';
import type { LibraryItem, RunItem, SettingsView } from './types';

type Screen = 'runs' | 'settings' | 'library';

export default function PipelineConsole() {
  const [phase, setPhase] = useState<'connect' | 'ready'>('connect');
  const [baseInput, setBaseInput] = useState(getBase());
  const [tokenInput, setTokenInput] = useState(getToken() ? '' : getToken());
  const [health, setHealth] = useState<'unknown' | 'ok' | 'dead'>('unknown');
  const [cfg, setCfg] = useState<SettingsView | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [lib, setLib] = useState<LibraryItem[]>([]);
  const [screen, setScreen] = useState<Screen>('runs');
  const [openRun, setOpenRun] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  const loadAll = useCallback(async () => {
    setErr(null);
    const [s, r, l] = await Promise.all([
      api.settings().catch((e) => { throw e; }),
      api.runs().catch(() => [] as RunItem[]),
      api.library().catch(() => [] as LibraryItem[]),
    ]);
    setCfg(s);
    setRuns(r);
    setLib(l);
  }, []);

  // Connect: address first (no auth), then the token against /settings.
  async function connect(e: { preventDefault(): void }) {
    e.preventDefault();
    setErr(null);
    setBase(baseInput);
    try {
      const h = await fetch(`${getBase()}/health`);
      if (!h.ok) throw new ApiError(h.status, `health check failed (${h.status})`);
      setHealth('ok');
    } catch (e2) {
      setHealth('dead');
      setErr(e2);
      return;
    }
    if (tokenInput.trim()) setToken(tokenInput);
    try {
      await loadAll(); // 401 ApiError on a bad token
      setPhase('ready');
    } catch (e2) {
      setErr(e2);
    }
  }

  // Strip + run-list refresh: poll while any run is busy, slowly otherwise.
  const anyBusy = runs.some((r) => busy(r.status));
  const pollRef = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (phase !== 'ready' || openRun) return;
    window.clearInterval(pollRef.current);
    const t = anyBusy ? 1500 : 8000;
    pollRef.current = window.setInterval(() => {
      api.runs().then(setRuns).catch(() => {});
    }, t);
    return () => window.clearInterval(pollRef.current);
  }, [phase, openRun, anyBusy]);

  const open = (id: string) => { setOpenRun(id); };
  const onStatusChange = useCallback(() => {
    api.runs().then(setRuns).catch(() => {});
    api.library().then(setLib).catch(() => {});
  }, []);

  if (phase === 'connect') {
    return (
      <div className="mx-auto max-w-xl py-10">
        <p className="px-font mb-3 text-[10px] text-muted">pipeline admin · local only</p>
        <h1 className="t-2 mb-8">Connect</h1>
        <form onSubmit={connect} className="px space-y-6 p-6 text-[13px]" id="connect-form">
          <Field label="pipeline api" hint="uv run pipeline serve prints the address">
            <input className={inputCls} value={baseInput} onChange={(e) => setBaseInput(e.target.value)} placeholder={API_DEFAULT} spellCheck={false} />
          </Field>
          <Field label="admin token" hint="same token the server printed (stays in localStorage)">
            <input className={inputCls} type="password" value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} placeholder="X-Admin-Token value" autoComplete="off" spellCheck={false} />
          </Field>
          <p className="meta">health: <span style={{ color: health === 'ok' ? 'var(--green)' : health === 'dead' ? 'var(--red)' : 'var(--muted)' }}>{health}</span></p>
          {err !== null && <ErrBox err={err} />}
          <p><button type="submit" className="btn btn-primary">connect</button></p>
        </form>
      </div>
    );
  }

  return (
    <div>
      {/* decision strip (§8.4) — always shows what Approve will do */}
      <section className="px my-4 flex flex-wrap items-center gap-x-8 gap-y-2 p-3 text-[12px]" id="status-strip" aria-label="Pipeline status">
        <span className="flex items-center gap-2"><i className="dot" style={{ background: 'var(--green)' }} aria-hidden="true" /> api {getBase().replace(/^https?:\/\//, '')}</span>
        <span style={{ color: 'var(--yellow)' }}>publish: {cfg?.publish_mode} · branch {cfg?.branch}</span>
        <span className="text-muted">approve → commit “content: …” & push origin {cfg?.branch}</span>
        <span className="ml-auto flex items-center gap-4">
          <Chip status="working">{runs.filter((r) => busy(r.status)).length} running</Chip>
          {needsDecision(runs[0]?.status ?? '') && <Chip status={runs[0].status}>decision needed</Chip>}
        </span>
      </section>

      <nav aria-label="Admin screens" className="mb-6 flex flex-wrap gap-2 text-[12px]">
        {(['runs', 'settings', 'library'] as Screen[]).map((s) => (
          <button key={s} type="button" className="tag tag-plain" role="tab" aria-selected={screen === s && !openRun}
                  style={screen === s && !openRun ? { background: 'var(--accent)', borderColor: 'var(--accent)', color: 'var(--bg)' } : undefined}
                  onClick={() => { setScreen(s); setOpenRun(null); }}>
            {s}{s === 'runs' && runs.some((r) => needsDecision(r.status)) ? ' ●' : ''}
          </button>
        ))}
        <button type="button" className="ml-auto btn btn-sm" onClick={() => { clearToken(); setTokenInput(''); setPhase('connect'); }}>disconnect</button>
      </nav>

      {openRun && <BlogReview runId={openRun} onExit={() => { setOpenRun(null); onStatusChange(); }} onStatusChange={onStatusChange} />}

      {!openRun && screen === 'runs' && (
        <div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
            <h1 className="t-2">Blog runs</h1>
            <button type="button" className="btn btn-sm" aria-pressed={showNew} onClick={() => setShowNew((v) => !v)}>{showNew ? 'close' : '+ new blog'}</button>
          </div>
          {showNew && <NewBlogForm defaultBudget={cfg?.default_budget_usd ?? 1} created={(id) => { setShowNew(false); api.runs().then(setRuns).catch(() => {}); open(id); }} />}
          <RunList runs={runs} open={open}
                   onDelete={async (id) => { try { await api.del(id); onStatusChange(); } catch (e) { setErr(e); } }} />
          {err !== null && <ErrBox err={err} />}
          <p className="meta mt-2">last sync {fmtTs(new Date().toISOString())} · caps {runs[0]?.budget_cap ? usd(runs[0].budget_cap) : '—'}</p>
        </div>
      )}

      {!openRun && screen === 'settings' && <Settings settings={cfg} reload={loadAll} />}
      {!openRun && screen === 'library' && <Library items={lib} />}
    </div>
  );
}
