// Model catalog browser + smoke tester (GET /models, POST /models/{id}/smoke).
import { useState } from 'react';
import { api } from '../api';
import { Chip, ErrBox, inputCls } from '../ui';
import type { ModelEntry } from '../types';

const fmtPrice = (n: number) => (n === 0 ? 'free' : `$${n < 1 ? n.toFixed(2) : n.toFixed(2)}/Mtok`);

export default function ModelPicker({ assign }: { assign: (id: string) => void }) {
  const [q, setQ] = useState('');
  const [freeOnly, setFreeOnly] = useState(true);
  const [structured, setStructured] = useState(false);
  const [items, setItems] = useState<ModelEntry[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [smoke, setSmoke] = useState<Record<string, { state: 'run' | 'ok' | 'bad'; ms?: number }>>({});

  async function search() {
    setLoading(true);
    setErr(null);
    try { setItems(await api.models(q, { free: freeOnly, structured })); }
    catch (e) { setErr(e); } finally { setLoading(false); }
  }

  async function test(mid: string) {
    setSmoke((s) => ({ ...s, [mid]: { state: 'run' } }));
    try {
      const r = await api.smoke(mid) as { latency_ms?: number };
      setSmoke((s) => ({ ...s, [mid]: { state: 'ok', ms: r.latency_ms } }));
    } catch {
      setSmoke((s) => ({ ...s, [mid]: { state: 'bad' } }));
    }
  }

  return (
    <div className="mt-6">
      <div className="flex flex-wrap items-end gap-4 text-[12px]">
        <input aria-label="model search" className={inputCls} style={{ maxWidth: '22rem' }} placeholder="search models…"
               value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') search(); }} />
        <label className="flex items-center gap-2 text-muted">
          <input type="checkbox" checked={freeOnly} onChange={(e) => setFreeOnly(e.target.checked)} style={{ accentColor: 'var(--accent)' }} /> free only
        </label>
        <label className="flex items-center gap-2 text-muted">
          <input type="checkbox" checked={structured} onChange={(e) => setStructured(e.target.checked)} style={{ accentColor: 'var(--accent)' }} /> structured output
        </label>
        <button type="button" className="btn btn-sm" onClick={search} disabled={loading}>{loading ? '…' : 'search catalog'}</button>
      </div>

      {err !== null && <ErrBox err={err} onRetry={search} />}
      {items && (
        <div className="my-4 max-h-96 overflow-auto" style={{ border: '4px solid var(--line)' }}>
          <table className="w-full text-[12px]">
            <thead className="sticky top-0 bg-surface-2">
              <tr className="text-muted"><th className="p-2 text-left">model</th><th className="p-2 text-right">in</th><th className="p-2 text-right">out</th><th className="p-2 text-left">ctx</th><th /></tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id} className="row border-t-2 border-dotted border-line align-middle">
                  <td className="p-2">
                    <span className="block font-mono text-[11px]">{m.id}</span>
                    {m.structured && <span className="meta">structured ✓</span>}
                  </td>
                  <td className="p-2 text-right text-muted">{fmtPrice(m.in_per_mtok)}</td>
                  <td className="p-2 text-right text-muted">{fmtPrice(m.out_per_mtok)}</td>
                  <td className="p-2 text-muted">{m.context_length ? `${Math.round(m.context_length / 1000)}k` : '—'}</td>
                  <td className="p-2">
                    <div className="flex justify-end gap-2">
                      {smoke[m.id] && <Chip status={smoke[m.id].state === 'ok' ? 'published' : smoke[m.id].state === 'bad' ? 'failed' : 'working'}>{smoke[m.id].state === 'run' ? 'smoking…' : smoke[m.id].state === 'bad' ? 'dead' : `${smoke[m.id].ms}ms`}</Chip>}
                      <button type="button" className="btn btn-sm" onClick={() => test(m.id)} disabled={smoke[m.id]?.state === 'run'}>smoke</button>
                      <button type="button" className="btn btn-sm btn-primary" onClick={() => assign(m.id)}>copy id</button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={5} className="p-4 text-muted">no models match</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      {!items && <p className="meta">Search the OpenRouter catalog, smoke-test a candidate, then copy its id into the console.</p>}
    </div>
  );
}
