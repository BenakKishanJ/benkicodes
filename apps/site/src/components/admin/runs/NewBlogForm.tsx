// Start a blog run (03-prd §5.1): topic, angle, sources, budget, plan checkpoint.
import { useState } from 'react';
import { api, ApiError, usd } from '../api';
import { ErrBox, Field, inputCls, taCls, Panel } from '../ui';

const lengths = ['short', 'medium', 'long'] as const;

export default function NewBlogForm({ created, defaultBudget }: {
  created: (id: string) => void;
  defaultBudget: number;
}) {
  const [topic, setTopic] = useState('');
  const [audience, setAudience] = useState('developers learning full-stack and AI engineering');
  const [angle, setAngle] = useState('');
  const [length, setLength] = useState<(typeof lengths)[number]>('medium');
  const [notes, setNotes] = useState('');
  const [checkpoint, setCheckpoint] = useState(true);
  const [budget, setBudget] = useState(String(defaultBudget));
  const [sources, setSources] = useState<{ kind: 'url' | 'text'; value: string }[]>([{ kind: 'url', value: '' }]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  const setSource = (i: number, patch: Partial<{ kind: 'url' | 'text'; value: string }>) =>
    setSources((ss) => ss.map((s, j) => (j === i ? { ...s, ...patch } : s)));

  const valid = topic.trim().length >= 3 && sources.some((s) => s.value.trim());

  async function submit(e: { preventDefault(): void }) {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const body = {
        topic: topic.trim(),
        audience: audience.trim(),
        angle: angle.trim() || undefined,
        length,
        notes: notes.trim(),
        checkpoint_plan: checkpoint,
        budget_usd: Number(budget) || undefined,
        sources: sources
          .filter((s) => s.value.trim())
          .map((s) => (s.kind === 'url'
            ? { kind: 'url', url: s.value.trim() }
            : { kind: 'text', title: s.value.split('\n')[0].slice(0, 60), text: s.value })),
      };
      const r = await api.newRun(body);
      created(r.id);
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2 : e2);
      setBusy(false);
    }
  }

  return (
    <Panel title="New blog run" className="max-w-3xl" id="new-blog-h">
      <form onSubmit={submit} className="space-y-6 text-[13px]">
        <Field label="topic" hint="what should the article cover?">
          <input className={inputCls} value={topic} onChange={(e) => setTopic(e.target.value)} required minLength={3} maxLength={200} />
        </Field>
        <Field label="audience">
          <input className={inputCls} value={audience} onChange={(e) => setAudience(e.target.value)} />
        </Field>
        <Field label="angle (optional)" hint="what should this offer that the top results don't?">
          <input className={inputCls} value={angle} onChange={(e) => setAngle(e.target.value)} />
        </Field>
        <div className="flex flex-wrap gap-8">
          <Field label="length">
            <select className={inputCls} value={length} onChange={(e) => setLength(e.target.value as (typeof lengths)[number])}>
              {lengths.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </Field>
          <Field label={`budget cap (${usd(budget)})`} hint="the run pauses if it spends more than this">
            <input className={inputCls} type="number" min="0.1" step="0.1" value={budget} onChange={(e) => setBudget(e.target.value)} />
          </Field>
          <Field label="plan checkpoint" hint="pause for your plan approval before drafting">
            <select className={inputCls} value={checkpoint ? 'yes' : 'no'} onChange={(e) => setCheckpoint(e.target.value === 'yes')}>
              <option value="yes">yes</option>
              <option value="no">no</option>
            </select>
          </Field>
        </div>
        <Field label="your notes" hint="your opinions and experience — the only place first-person claims may come from">
          <textarea className={taCls} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
        <fieldset>
          <legend className="px-font mb-3 text-[10px] text-muted">sources (1 to 12)</legend>
          <div className="space-y-3">
            {sources.map((s, i) => (
              <div key={i} className="flex flex-wrap items-center gap-3">
                <select aria-label={`source ${i + 1} kind`} className={inputCls} style={{ width: '6.5rem' }}
                        value={s.kind} onChange={(e) => setSource(i, { kind: e.target.value as 'url' | 'text' })}>
                  <option value="url">url</option>
                  <option value="text">text</option>
                </select>
                {s.kind === 'url'
                  ? <input className={inputCls} style={{ flex: 1 }} placeholder="https://…" value={s.value} onChange={(e) => setSource(i, { value: e.target.value })} />
                  : <textarea className={taCls} style={{ flex: 1 }} rows={2} placeholder="paste the text to ground the article in" value={s.value} onChange={(e) => setSource(i, { value: e.target.value })} />}
                {sources.length > 1 && (
                  <button type="button" className="icon-btn" aria-label={`remove source ${i + 1}`}
                          onClick={() => setSources((ss) => ss.filter((_, j) => j !== i))}>×</button>
                )}
              </div>
            ))}
          </div>
          <button type="button" className="btn btn-sm mt-4" onClick={() => setSources((ss) => [...ss, { kind: 'url', value: '' }])}>
            + add source
          </button>
        </fieldset>

        {err !== null && <ErrBox err={err} />}
        <p>
          <button type="submit" className="btn btn-primary" disabled={!valid || busy}>
            {busy ? 'starting…' : 'start run'}
          </button>
        </p>
      </form>
    </Panel>
  );
}
