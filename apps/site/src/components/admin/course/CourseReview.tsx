// Course review (planning interrupts): live activity, references review,
// course-plan review, and the planning-done repo summary (03-prd §7.3).
// Part-loop screens (PartWorkspace, LessonReview) join this file in Phase B.
import { useState } from 'react';
import { api, fmtTs, usd } from '../api';
import { Chip, ErrBox, Field, inputCls, Panel, taCls } from '../ui';
import { useLiveRun } from '../useLiveRun';
import type { CoursePlanView, CourseRef, CourseRunView, RefsDecision, CoursePlanDecision } from '../types';

// ---------------------------------------------------------------- refs review
function RefsReview({ course, onSend, sending }: {
  course: CourseRunView;
  onSend: (d: RefsDecision) => void;
  sending: boolean;
}) {
  const refs = course.refs ?? [];
  const [keep, setKeep] = useState<string[]>(refs.map((r) => r.id)); // default: keep everything
  const [inspired, setInspired] = useState<string[]>([]);
  const [added, setAdded] = useState<{ title: string; url: string; type: string; why: string }[]>([]);
  const toggle = (id: string, list: string[], set: (x: string[]) => void) =>
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  const valid = keep.length >= 1 || added.length >= 1;

  return (
    <Panel title="References checkpoint" id="refs-h">
      <p className="meta mb-4">Tick what to keep (planning uses only these), mark “inspired by” credits for the course page, and add your own references if the search missed something.</p>
      <ul className="space-y-2.5 text-[12px]">
        {refs.map((r: CourseRef) => (
          <li key={r.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-dotted border-line pb-2.5">
            <input type="checkbox" className="mt-1" checked={keep.includes(r.id)} aria-label={`keep ${r.title}`} onChange={() => toggle(r.id, keep, setKeep)} />
            <span className="mono-kbd">{r.id}</span>
            <span className="min-w-0 flex-1">
              <a className="underline decoration-dashed underline-offset-4 hover:text-accent" href={r.url} rel="noopener noreferrer" target="_blank">{r.title || r.url}</a>
              <span className="block text-muted">{r.type}{r.level ? ` · ${r.level}` : ''}{r.illustrated ? ' · illustrated' : ''}{r.verified === false ? ' · unverified ⚠' : ''}{r.why ? ` — ${r.why}` : ''}</span>
            </span>
            <label className="flex items-center gap-2 text-[12px]">
              <input type="checkbox" checked={inspired.includes(r.id)} aria-label={`inspired by ${r.title}`} onChange={() => toggle(r.id, inspired, setInspired)} />
              <span className="px-font text-[10px] text-muted">inspired-by</span>
            </label>
          </li>
        ))}
        {refs.length === 0 && <li className="text-muted">No references found — add at least one below.</li>}
      </ul>

      <p className="px-font mt-6 mb-3 text-[10px] text-muted">add your own</p>
      <div className="space-y-3">
        {added.map((a, i) => (
          <div key={i} className="flex flex-wrap items-center gap-3">
            <input aria-label={`added reference ${i + 1} url`} className={inputCls} style={{ flex: 1, minWidth: '14rem' }} value={a.url}
                   placeholder="https://…" inputMode="url" spellCheck={false}
                   onChange={(e) => setAdded((xs) => xs.map((x, j) => (j === i ? { ...x, url: e.target.value } : x)))} />
            <input aria-label={`added reference ${i + 1} title`} className={inputCls} style={{ width: '14rem' }} value={a.title} placeholder="title"
                   onChange={(e) => setAdded((xs) => xs.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))} />
            <select aria-label={`added reference ${i + 1} type`} className={inputCls} style={{ width: '7rem' }} value={a.type}
                    onChange={(e) => setAdded((xs) => xs.map((x, j) => (j === i ? { ...x, type: e.target.value } : x)))}>
              {['article', 'repo', 'video', 'docs', 'interactive', 'book', 'course', 'roadmap'].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input aria-label={`added reference ${i + 1} why`} className={inputCls} style={{ width: '16rem' }} value={a.why} placeholder="why it helps"
                   onChange={(e) => setAdded((xs) => xs.map((x, j) => (j === i ? { ...x, why: e.target.value } : x)))} />
            <button type="button" className="icon-btn" aria-label={`remove added reference ${i + 1}`}
                    onClick={() => setAdded((xs) => xs.filter((_, j) => j !== i))}>×</button>
          </div>
        ))}
      </div>
      <button type="button" className="btn btn-sm mt-4" onClick={() => setAdded((xs) => [...xs, { title: '', url: '', type: 'article', why: '' }])}>
        + add reference
      </button>

      <p className="mt-6 flex flex-wrap gap-4">
        <button type="button" className="btn btn-primary btn-sm" disabled={!valid || sending}
                onClick={() => onSend({ keep, added, inspired_by: inspired })}>
          {sending ? 'locking…' : 'lock references → plan the course'}
        </button>
      </p>
    </Panel>
  );
}

// ---------------------------------------------------------------- plan review
function PlanReview({ course, onSend, sending, comments, setComments }: {
  course: CourseRunView;
  onSend: (d: CoursePlanDecision) => void;
  sending: boolean;
  comments: string;
  setComments: (v: string) => void;
}) {
  const plan: CoursePlanView | null = course.plan;
  if (!plan) return null;
  const p = plan.project;
  return (
    <Panel title="Course plan checkpoint" id="course-plan-h">
      <p className="meta mb-4">Approve to freeze slugs, order and the repo scaffold — or request changes (your comments go back to the planner).</p>

      <div className="mb-6 text-[13px]">
        <p><span className="px-font text-[10px] text-muted">you will build</span><br /><span className="text-fg">{p.name}</span> — {p.summary}</p>
        <p className="mt-3"><span className="px-font text-[10px] text-muted">stack</span><br />{p.stack.join(' · ')}</p>
        <p className="mt-3"><span className="px-font text-[10px] text-muted">final features</span><br />{p.final_features.join(' · ')}</p>
      </div>

      <ol className="space-y-4 text-[12px]">
        {plan.parts.map((part) => (
          <li key={part.n} className="px p-4">
            <p className="flex flex-wrap items-baseline gap-3">
              <span className="mono-kbd">part-{part.n}</span>
              <span className="text-fg">{part.title}</span>
              <span className="text-muted">/{part.slug} · ~{part.estimatedMinutes} min</span>
            </p>
            <p className="mt-2 text-muted"><span className="px-font text-[10px]">objectives:</span> {part.objectives.join(' · ')}</p>
            {(part.concepts?.length ?? 0) > 0 && <p className="mt-1.5 text-muted"><span className="px-font text-[10px]">concepts:</span> {(part.concepts ?? []).join(' · ')}</p>}
            <p className="mt-2"><span className="px-font text-[10px] text-muted">commits:</span></p>
            <ol className="mt-1 space-y-1.5">
              {part.steps.map((s, i) => (
                <li key={i} className="flex gap-3">
                  <span className="font-mono text-[10px]" style={{ color: 'var(--accent)' }}>{i + 1}.</span>
                  <span><span className="text-fg">{s.title}</span><span className="text-muted"> — {s.intent}{s.files?.length ? ` (${s.files.join(', ')})` : ''}</span></span>
                </li>
              ))}
            </ol>
            <p className="mt-2 text-muted">
              {(part.doc_urls?.length ?? 0) > 0 && <>docs: {part.doc_urls?.map((u) => u.replace(/^https?:\/\//, '')).join(', ')} · </>}
              {(part.ref_ids?.length ?? 0) > 0 && <>refs: {part.ref_ids?.map((r) => `${r}${part.resource_notes?.[r] ? ` (${part.resource_notes[r]})` : ''}`).join(', ')}</>}
            </p>
          </li>
        ))}
      </ol>

      {course.plan_feedback.length > 0 && (
        <p className="meta mt-4">previous feedback: {course.plan_feedback.join(' | ')}</p>
      )}
      <p className="mt-5"><Field label="comments (one per line)"><textarea className={taCls} rows={2} value={comments} onChange={(e) => setComments(e.target.value)} /></Field></p>
      <p className="mt-4 flex gap-4">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => onSend({ action: 'approve', comments: [] })} disabled={sending}>
          {sending ? 'creating repo…' : 'approve plan → create repo'}
        </button>
        <button type="button" className="btn btn-sm" onClick={() => onSend({ action: 'changes', comments: comments.split('\n').map((c) => c.trim()).filter(Boolean) })} disabled={sending || !comments.trim()}>
          request changes
        </button>
      </p>
    </Panel>
  );
}

// ---------------------------------------------------------------- run review shell
export default function CourseReview({ runId, onExit, onStatusChange }: {
  runId: string;
  onExit: () => void;
  onStatusChange: () => void;
}) {
  const { run, err, refresh, setErr } = useLiveRun(runId, onStatusChange);
  const [sending, setSending] = useState<string | null>(null);
  const [comments, setComments] = useState('');
  const [budgetInput, setBudgetInput] = useState('');

  if (!run && !err) return <p className="meta m-6">loading run {runId}…</p>;

  const st = run?.status ?? 'loading';
  const u = run?.usage;
  const warnColor = u?.budget?.warn ? 'var(--yellow)' : 'var(--muted)';
  const course = run?.course ?? null;

  async function send(body: RefsDecision | CoursePlanDecision, tag: string) {
    setSending(tag);
    setErr(null);
    try {
      await api.resume(runId, body);
      await refresh();
      onStatusChange();
      setComments('');
    } catch (e) {
      setErr(e);
    } finally {
      setSending(null);
    }
  }

  async function raiseBudget() {
    const cap = Number(budgetInput);
    if (!cap) return;
    setSending('budget');
    setErr(null);
    try {
      await api.budget(runId, cap);
      await refresh();
      setBudgetInput('');
    } catch (e) { setErr(e); } finally { setSending(null); }
  }

  async function retry() {
    setSending('retry');
    setErr(null);
    try {
      await api.retry(runId);
      await refresh();
      onStatusChange();
    } catch (e) { setErr(e); } finally { setSending(null); }
  }

  return (
    <div>
      <section className="px my-3 flex flex-wrap items-center gap-x-8 gap-y-2 p-4 text-[12px]">
        <button type="button" className="btn btn-sm" onClick={onExit}>← runs</button>
        <Chip status={st}>{st}</Chip>
        <span className="text-fg">{run?.topic ?? runId}</span>
        <span className="text-muted">course · run {runId}</span>
        <span style={{ color: warnColor }}>spent {usd(u?.budget?.spent ?? 0)} / {usd(u?.budget?.cap ?? 0)}</span>
      </section>

      {err !== null && <ErrBox err={err} onRetry={refresh} />}

      {run && st === 'failed' && (
        <Panel title="Run failed" id="c-failed-h">
          <p className="font-mono text-[12px]" style={{ color: 'var(--red)' }}>{run.error}</p>
          <button type="button" className="btn btn-sm mt-4" onClick={retry} disabled={sending === 'retry'}>
            {sending === 'retry' ? 'retrying…' : 'retry from last checkpoint'}
          </button>
        </Panel>
      )}

      {run && st === 'paused_budget' && (
        <Panel title="Budget pause" id="c-paused-h">
          <p className="meta">The run hit its {usd(u?.budget?.cap ?? 0)} cap and paused. Raise the cap — it resumes automatically.</p>
          <p className="mt-4 flex flex-wrap items-end gap-4">
            <Field label={`new cap (spent ${usd(u?.budget?.spent ?? 0)})`}>
              <input className={inputCls} style={{ width: '9rem' }} type="number" min="0.1" step="0.1"
                     value={budgetInput} onChange={(e) => setBudgetInput(e.target.value)} placeholder={String((u?.budget?.cap ?? 1) + 0.5)} />
            </Field>
            <button type="button" className="btn btn-sm" onClick={raiseBudget} disabled={sending === 'budget' || !Number(budgetInput)}>
              {sending === 'budget' ? 'raising…' : 'raise & resume'}
            </button>
          </p>
        </Panel>
      )}

      {run && st === 'planning_done' && course?.repo && (
        <Panel title="Planning done" id="c-done-h">
          <ul className="space-y-2 text-[13px]">
            <li><span className="text-muted">repo:</span> <span className="font-mono text-accent">{course.repo.path}</span></li>
            <li><span className="text-muted">package:</span> <span className="font-mono">{course.repo.package}</span></li>
            <li><span className="text-muted">remote:</span> {course.repo.remote_url ?? '(none yet)'} {course.repo.remote_ok === false && <span style={{ color: 'var(--yellow)' }}>— not verified</span>}{course.repo.empty_ok === true && ' (reachable, empty ✓)'}</li>
            <li><span className="text-muted">tags:</span> <span className="font-mono">{(course.repo.tagged ?? []).join(', ')}</span></li>
          </ul>
          <p className="meta mt-4">The part loop (code → lesson → review → publish) lands in Phase B — this repo is set up and waiting.</p>
          <p className="meta">docs feed: {course.docs?.length ?? 0} official pages · refs kept: {course.refs?.length ?? 0}</p>
        </Panel>
      )}

      {course && run?.pending?.type === 'refs' && (
        <RefsReview course={course} sending={sending === 'refs'} onSend={(d) => send(d, 'refs')} />
      )}

      {course && run?.pending?.type === 'course_plan' && (
        <PlanReview course={course} sending={sending === 'plan'} onSend={(d) => send(d, 'plan')}
                    comments={comments} setComments={setComments} />
      )}

      {run && (
        <Panel title="Activity & calls" id="c-activity-h">
          <ol className="max-h-72 space-y-1.5 overflow-auto font-mono text-[11px]">
            {run.events.map((e, i) => (
              <li key={`${e.t}-${i}`} style={e.level === 'warn' ? { color: 'var(--yellow)' } : e.level === 'err' || e.level === 'error' ? { color: 'var(--red)' } : i === run.events.length - 1 ? { color: 'var(--fg)' } : { color: 'var(--muted)' }}>
                <span className="text-muted">{e.t.slice(11, 19)}</span> <span style={{ color: 'var(--accent)' }}>[{e.node}]</span> {e.msg}
              </li>
            ))}
          </ol>
          <details className="mt-4">
            <summary className="px-font text-[10px] text-muted">recent model calls ({run.calls.length})</summary>
            <pre className="mt-3 max-h-72 overflow-auto p-3 font-mono text-[11px]">{JSON.stringify(run.calls, null, 2)}</pre>
          </details>
          <p className="meta mt-3">updated {fmtTs(run.updated_at)}</p>
        </Panel>
      )}
    </div>
  );
}
