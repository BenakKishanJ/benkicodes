// Read-only settings view (GET /settings, /credits) + model catalog picker.
// Task routing is edited in apps/pipeline/config/models.yaml for now (03-prd §9).
import { useEffect, useState } from 'react';
import { api, fmtTs, usd } from '../api';
import { ErrBox, Panel } from '../ui';
import type { SettingsView } from '../types';
import ModelPicker from './ModelPicker';

export default function Settings({ settings, reload }: { settings: SettingsView | null; reload: () => void }) {
  const [credits, setCredits] = useState<unknown>(null);
  const [err, setErr] = useState<unknown>(null);
  const [copied, setCopied] = useState('');

  useEffect(() => {
    api.credits().then(setCredits).catch((e) => setErr(e));
  }, []);

  const assign = async (mid: string) => {
    try { await navigator.clipboard.writeText(mid); } catch { /* clipboard may be blocked */ }
    setCopied(mid);
    window.setTimeout(() => setCopied(''), 1800);
  };

  const total = credits && typeof credits === 'object' ? (credits as Record<string, number>).total_credits : undefined;
  const usageTotal = credits && typeof credits === 'object' ? (credits as Record<string, number>).total_usage : undefined;

  return (
    <div>
      <Panel title="Task routing" id="tasks-h" className="max-w-3xl">
        {settings?.api_key_configured === false && (
          <p className="mb-4 text-[12px]" style={{ color: 'var(--red)' }}>OPENROUTER_API_KEY is not configured on the server.</p>
        )}
        <table className="w-full text-[12px]">
          <tbody>
            {Object.entries(settings?.tasks ?? {}).map(([task, t]) => (
              <tr key={task} className="border-b-2 border-dotted border-line">
                <td className="py-2 pr-4 px-font text-[10px] text-muted">{task}</td>
                <td className="py-2 font-mono text-[11px]">{t.model}</td>
                <td className="py-2 text-muted">{(t.fallbacks ?? []).join(' · ') || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="meta mt-3">
          Routing is edited in <code className="kbd">apps/pipeline/config/models.yaml</code>, then restart <code className="kbd">pipeline serve</code>.
        </p>
        <ModelPicker assign={assign} />
        {copied && <p className="meta">copied <span className="font-mono text-accent">{copied}</span> — paste it into models.yaml / New blog run notes.</p>}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Budgets" id="budgets-h">
          <dl className="spec">
            <div><dt>default per-run cap</dt><dd>{usd(settings?.default_budget_usd)}</dd></div>
          </dl>
        </Panel>
        <Panel title="Publishing" id="publish-h">
          <dl className="spec">
            <div><dt>mode</dt><dd>{settings?.publish_mode}</dd></div>
            <div><dt>branch</dt><dd>{settings?.branch}</dd></div>
            <div><dt>site url</dt><dd>{settings?.site_base_url}</dd></div>
            <div><dt>plan checkpoint</dt><dd>{settings?.checkpoint_plan ? 'on' : 'off'}</dd></div>
          </dl>
        </Panel>
        <Panel title="OpenRouter credits" id="credits-h">
          {err !== null && <ErrBox err={err} label="reload" />}
          {credits !== null && typeof credits === 'object' && (
            <dl className="spec">
              <div><dt>total credits</dt><dd>{typeof total === 'number' ? `$${total.toFixed(2)}` : JSON.stringify(credits)}</dd></div>
              {typeof usageTotal === 'number' && <div><dt>used so far</dt><dd className="mono-kbd">${usageTotal.toFixed(4)}</dd></div>}
            </dl>
          )}
          <button type="button" className="btn btn-sm mt-3" onClick={reload}>refresh settings</button>
        </Panel>
      </div>

      <p className="meta">settings fetched {fmtTs(new Date().toISOString())} — read-only; secrets never leave the pipeline.</p>
    </div>
  );
}
