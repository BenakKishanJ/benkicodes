// Start a course run (03-prd §7.3 intake): subject, level, official docs URLs,
// part-count range, repo name + remote, budget. Mirrors NewBlogForm patterns.
import { useState } from 'react';
import { api, ApiError, usd } from '../api';
import { ErrBox, Field, inputCls, taCls, Panel } from '../ui';

const levels = ['beginner', 'intermediate', 'advanced'] as const;

export default function CourseForm({ created, defaultBudget }: {
  created: (id: string) => void;
  defaultBudget: number;
}) {
  const [subject, setSubject] = useState('');
  const [level, setLevel] = useState<(typeof levels)[number]>('intermediate');
  const [minParts, setMinParts] = useState('2');
  const [maxParts, setMaxParts] = useState('6');
  const [hints, setHints] = useState('');
  const [repoName, setRepoName] = useState('');
  const [remote, setRemote] = useState('');
  const [budget, setBudget] = useState(String(defaultBudget));
  const [docs, setDocs] = useState<string[]>(['']);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  const setDoc = (i: number, value: string) => setDocs((ds) => ds.map((d, j) => (j === i ? value : d)));

  const valid = subject.trim().length >= 3 && docs.some((d) => d.trim().startsWith('http'))
    && repoName.trim().length >= 3
    && Number(minParts) >= 1 && Number(maxParts) >= Number(minParts);

  async function submit(e: { preventDefault(): void }) {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.newRun({
        mode: 'course',
        subject: subject.trim(),
        level,
        docs_urls: docs.filter((d) => d.trim().startsWith('http')).map((d) => d.trim()),
        min_parts: Number(minParts),
        max_parts: Number(maxParts),
        hints: hints.trim(),
        repo_name: repoName.trim(),
        remote_url: remote.trim().startsWith('http') ? remote.trim() : undefined,
        budget_usd: Number(budget) || undefined,
      });
      created(r.id);
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2 : e2);
      setBusy(false);
    }
  }

  return (
    <Panel title="New course run" className="max-w-3xl" id="new-course-h">
      <form onSubmit={submit} className="space-y-6 text-[13px]">
        <Field label="subject" hint="what will the learner build? e.g. “a deep-research agent with LangGraph”">
          <input className={inputCls} value={subject} onChange={(e) => setSubject(e.target.value)} required minLength={3} maxLength={200} />
        </Field>
        <div className="flex flex-wrap gap-8">
          <Field label="level">
            <select className={inputCls} value={level} onChange={(e) => setLevel(e.target.value as (typeof levels)[number])}>
              {levels.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </Field>
          <Field label="parts (min)">
            <input className={inputCls} type="number" min="1" max="20" value={minParts} onChange={(e) => setMinParts(e.target.value)} style={{ width: '6rem' }} />
          </Field>
          <Field label="parts (max)">
            <input className={inputCls} type="number" min="1" max="20" value={maxParts} onChange={(e) => setMaxParts(e.target.value)} style={{ width: '6rem' }} />
          </Field>
          <Field label={`budget cap (${usd(budget)})`} hint="the run pauses if it spends more than this">
            <input className={inputCls} type="number" min="0.1" step="0.1" value={budget} onChange={(e) => setBudget(e.target.value)} style={{ width: '7rem' }} />
          </Field>
        </div>
        <Field label="official docs urls" hint="the ground truth the lessons will cite; 1-8 urls, related pages are crawled one level">
          <div className="space-y-3">
            {docs.map((d, i) => (
              <div key={i} className="flex items-center gap-3">
                <input className={inputCls} style={{ flex: 1 }} placeholder="https://…/docs" inputMode="url" spellCheck={false}
                       value={d} onChange={(e) => setDoc(i, e.target.value)} />
                {docs.length > 1 && (
                  <button type="button" className="icon-btn" aria-label={`remove docs url ${i + 1}`}
                          onClick={() => setDocs((ds) => ds.filter((_, j) => j !== i))}>×</button>
                )}
              </div>
            ))}
          </div>
          <button type="button" className="btn btn-sm mt-4" onClick={() => setDocs((ds) => [...ds, ''])}>+ add docs url</button>
        </Field>
        <div className="flex flex-wrap gap-8">
          <Field label="repo name" hint="folder under ../courses/ and the GitHub repo name, e.g. langgraph-deep-research">
            <input className={inputCls} value={repoName} onChange={(e) => setRepoName(e.target.value)} required spellCheck={false} minLength={3} maxLength={80} style={{ width: '18rem' }} />
          </Field>
          <Field label="github remote (optional)" hint="create an EMPTY public repo first; the pipeline only verifies it">
            <input className={inputCls} value={remote} onChange={(e) => setRemote(e.target.value)} placeholder="https://github.com/you/…" spellCheck={false} style={{ width: '24rem' }} />
          </Field>
        </div>
        <Field label="hints (optional)" hint="your opinions and constraints — the only place first-person input comes from">
          <textarea className={taCls} rows={3} value={hints} onChange={(e) => setHints(e.target.value)} />
        </Field>

        {err !== null && <ErrBox err={err} />}
        <p>
          <button type="submit" className="btn btn-primary" disabled={!valid || busy}>
            {busy ? 'starting…' : 'start course'}
          </button>
        </p>
      </form>
    </Panel>
  );
}
