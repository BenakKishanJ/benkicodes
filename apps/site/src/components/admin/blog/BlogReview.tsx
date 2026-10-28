// Blog review: live activity, plan checkpoint, and the tabbed draft review with
// approve / request changes / reject + budget and retry controls (03-prd §9).
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, fmtTs, streamRun, terminal, usd, type StreamFrame } from '../api';
import { Chip, ConfirmButton, ErrBox, Field, inputCls, Panel, taCls } from '../ui';
import type { PlanDecision, ReviewDecision, RunView, SeoView } from '../types';

const TABS = ['draft', 'sources', 'checks', 'diff', 'metadata'] as const;
type Tab = (typeof TABS)[number];

export default function BlogReview({ runId, onExit, onStatusChange }: {
  runId: string;
  onExit: () => void;
  onStatusChange: () => void;
}) {
  const [run, setRun] = useState<RunView | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [tab, setTab] = useState<Tab>('draft');
  const [comments, setComments] = useState('');
  const [editedMd, setEditedMd] = useState<{ on: boolean; text: string }>({ on: false, text: '' });
  const [seoEdit, setSeoEdit] = useState<SeoView | null>(null);
  const [force, setForce] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState<string | null>(null);
  const [budgetInput, setBudgetInput] = useState('');
  const onStatusRef = useRef(onStatusChange);
  onStatusRef.current = onStatusChange;

  const refresh = useCallback(async (): Promise<RunView | null> => {
    try {
      const v = await api.run(runId);
      setRun(v);
      setErr(null);
      return v;
    } catch (e) {
      setErr(e);
      return null;
    }
  }, [runId]);

  useEffect(() => { setRun(null); setTab('draft'); setComments(''); setEditedMd({ on: false, text: '' }); setSeoEdit(null); setForce(false); setConfirming(false); refresh(); }, [runId, refresh]);

  // Live view: SSE while the run works; poll fallback if the stream fails.
  // Live view: SSE while anything non-decision/non-terminal is happening —
  // not just busy() statuses (transitional ones like "gating" would strand it).
  const needStream = !!run && !run.pending && !terminal(run.status);
  useEffect(() => {
    if (!needStream) return;
    let cancelled = false;
    let poll: number | undefined;
    let first = true;
    const cancel = streamRun(
      runId,
      (f: StreamFrame) => {
        // First frame replays the full history (server starts sent_n at 0);
        // later frames carry only fresh events. `pending` rides every frame so
        // an interrupt arriving while you watch flips the decision panel live.
        const wasFirst = first;
        first = false;
        setRun((r) => (r ? {
          ...r,
          status: f.status,
          events: wasFirst ? f.events : [...r.events, ...f.events],
          pending: f.pending ? { type: f.pending } : r.pending,
          usage: r.usage.budget ? { ...r.usage, budget: { ...r.usage.budget, spent: f.spent } } : r.usage,
        } : r));
      },
      () => { // server-reported terminal state
        if (cancelled) return;
        onStatusRef.current();
        refresh();
      },
      () => { // stream failed (e.g. buffered proxy) -> gentle polling
        poll = window.setInterval(async () => {
          const v = await refresh();
          if (v && (terminal(v.status) || v.pending)) {
            window.clearInterval(poll);
            onStatusRef.current();
          }
        }, 2000);
      },
    );
    return () => { cancelled = true; if (poll !== undefined) window.clearInterval(poll); cancel(); };
  }, [runId, needStream, refresh]);

  const dec = (comments2: string) => comments2.split('\n').map((c) => c.trim()).filter(Boolean);

  async function sendPlan(action: 'approve' | 'revise') {
    const body: PlanDecision = { action, comments: dec(comments) };
    await decide(`runs/${runId}/resume`, body);
  }

  async function sendReview(action: 'approve' | 'changes' | 'reject') {
    if (action === 'approve' && !confirming) { setConfirming(true); return; }
    setConfirming(false);
    const body: ReviewDecision = {
      action,
      comments: dec(comments),
      edited_md: editedMd.on ? editedMd.text : undefined,
      force: force || undefined,
      ...(seoEdit ? { seo: seoEdit as unknown as Record<string, unknown> } : {}),
    };
    await decide(`runs/${runId}/resume`, body);
  }

  async function decide(path: string, body: unknown) {
    setSending(path);
    setErr(null);
    try {
      await api.resume(runId, body);
      await refresh();
      onStatusChange();
      setComments('');
      setEditedMd({ on: false, text: '' });
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
    try { await api.retry(runId); await refresh(); onStatusChange(); }
    catch (e) { setErr(e); } finally { setSending(null); }
  }

  if (!run && !err) return <p className="meta m-6">loading run {runId}…</p>;

  const st = run?.status ?? 'loading';
  const u = run?.usage;
  const warnColor = u?.budget?.warn ? 'var(--yellow)' : 'var(--muted)';
  const gatesBlocking = (run?.gates ?? []).some((g) => g.status === 'fail');

  return (
    <div>
      {/* decision strip (§8.4): status, spend, what approving does */}
      <section className="px my-3 flex flex-wrap items-center gap-x-8 gap-y-2 p-4 text-[12px]">
        <button type="button" className="btn btn-sm" onClick={onExit}>← runs</button>
        <Chip status={st}>{st}</Chip>
        <span className="text-fg">{run?.topic ?? runId}</span>
        <span className="text-muted">run {runId}</span>
        <span style={{ color: warnColor }}>spent {usd(u?.budget?.spent ?? 0)} / {usd(u?.budget?.cap ?? 0)}</span>
        <span className="text-muted">rev {run?.revision_count ?? 0} · rounds {run?.human_rounds ?? 0}</span>
      </section>

      {err !== null && <ErrBox err={err} onRetry={refresh} />}

      {run && st === 'failed' && (
        <Panel title="Run failed" id="failed-h">
          <p className="font-mono text-[12px]" style={{ color: 'var(--red)' }}>{run.error}</p>
          <button type="button" className="btn btn-sm mt-4" onClick={retry} disabled={sending === 'retry'}>
            {sending === 'retry' ? 'retrying…' : 'retry from last checkpoint'}
          </button>
        </Panel>
      )}

      {run && st === 'paused_budget' && (
        <Panel title="Budget pause" id="paused-h">
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

      {run && st === 'published' && (
        <Panel title="Published" id="published-h">
          <ul className="space-y-2 text-[13px]">
            {Object.entries(run.published ?? {}).map(([k, v]) => (
              <li key={k}><span className="text-muted">{k}:</span> <span className="font-mono text-accent">{String(v)}</span></li>
            ))}
          </ul>
        </Panel>
      )}

      {run && run.pending?.type === 'plan' && run.plan && (
        <Panel title="Plan checkpoint" id="plan-h">
          <p className="meta mb-4">What will be written. Approve, or request changes — your comments go back to the planner.</p>
          <div className="mb-4 text-[13px]">
            <p><span className="px-font text-[10px] text-muted">angle</span><br />{run.plan.angle}</p>
            <p className="mt-3"><span className="px-font text-[10px] text-muted">working title</span><br />{run.plan.working_title}</p>
          </div>
          <table className="w-full text-[12px]">
            <thead><tr><th className="py-1.5 text-left">section</th><th className="py-1.5 text-left">goal</th></tr></thead>
            <tbody>
              {run.plan.sections?.map((s, i) => (
                <tr key={i} className="border-b-2 border-dotted border-line">
                  <td className="py-2 pr-6 align-top">{s.heading}</td>
                  <td className="py-2 align-top text-muted">{s.goal}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {run.plan_feedback.length > 0 && (
            <p className="meta mt-4">previous feedback: {run.plan_feedback.join(' | ')}</p>
          )}
          <p className="mt-5"><Field label="comments (one per line)"><textarea className={taCls} rows={2} value={comments} onChange={(e) => setComments(e.target.value)} /></Field></p>
          <p className="mt-4 flex gap-4">
            <button type="button" className="btn btn-primary btn-sm" onClick={() => sendPlan('approve')} disabled={!!sending}>approve plan</button>
            <button type="button" className="btn btn-sm" onClick={() => sendPlan('revise')} disabled={!!sending}>request changes</button>
          </p>
        </Panel>
      )}

      {run && run.pending?.type === 'review' && (
        <>
          <nav aria-label="Review tabs" className="mx-2 mt-4 flex flex-wrap gap-2 text-[12px]">
            {TABS.map((t) => (
              <button key={t} type="button" className="tag tag-plain" role="tab" aria-selected={tab === t}
                      style={tab === t ? { background: 'var(--accent)', borderColor: 'var(--accent)', color: 'var(--bg)' } : undefined}
                      onClick={() => setTab(t)}>{t}</button>
            ))}
            <button type="button" className="tag tag-plain" onClick={() => setEditedMd((e) => ({ ...e, on: !e.on }))}
                    style={editedMd.on ? { borderColor: 'var(--yellow)', color: 'var(--yellow)' } : undefined} aria-pressed={editedMd.on}>
              {editedMd.on ? 'editing on' : 'edit markdown'}
            </button>
          </nav>

          {tab === 'draft' && (
            <section className="my-3" aria-label="Draft" id="draft-h">
              {editedMd.on ? (
                <Field label="draft markdown (your edits are authoritative)">
                  <textarea className={`${taCls} min-h-[28rem] text-[12.5px]`} value={editedMd.text || run.draft_md} onChange={(e) => setEditedMd({ on: true, text: e.target.value })} rows={22} />
                </Field>
              ) : (
                <article className="prose mx-auto my-6" id="draft-preview" dangerouslySetInnerHTML={{ __html: run.draft_html }} />
              )}
            </section>
          )}

          {tab === 'sources' && (
            <Panel title="Sources" id="sources-tab-h">
              <ul className="space-y-3 text-[12px]">
                {run.sources.map((s) => (
                  <li key={s.id} className="flex flex-wrap items-baseline gap-3">
                    <span className="mono-kbd">{s.id}</span>
                    <span>{s.title}</span>
                    <span className="text-muted">· {s.trust}{s.flags.length > 0 && `, ${s.flags.join(', ')}`}</span>
                    <a className="underline decoration-dashed underline-offset-4 hover:text-accent" href={s.url ?? '#'} rel="noopener noreferrer" target="_blank">link</a>
                    <span className="text-muted">{s.chars} chars</span>
                    <span className="block w-full font-mono text-[11px] text-muted">{s.excerpt}…</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {tab === 'checks' && (
            <Panel title="Checks & gates" id="checks-tab-h">
              {run.check?.scores && (
                <ul className="mb-6 flex flex-wrap gap-3 text-[12px]">
                  {Object.entries(run.check.scores).map(([k, v]) => (
                    <li key={k} className="kbd" style={v < 3 ? { color: 'var(--red)' } : v === 3 ? { color: 'var(--yellow)' } : undefined}>{k}: {v}/5</li>
                  ))}
                </ul>
              )}
              {(run.check?.unsupported_claims?.length ?? 0) > 0 && (
                <div className="mb-6">
                  <p className="px-font mb-2 text-[10px]" style={{ color: 'var(--red)' }}>unsupported claims</p>
                  <ul className="list-disc pl-6 text-[12px]">{run.check?.unsupported_claims?.map((c, i) => <li key={i}>{c}</li>)}</ul>
                </div>
              )}
              {(run.check?.issues ?? []).length > 0 && (
                <ul className="mb-6 space-y-3 text-[12px]">
                  {run.check?.issues?.map((i2, j) => (
                    <li key={j} className="opt">
                      <span className="mark" style={{ background: i2.severity === 'high' ? 'var(--red)' : i2.severity === 'medium' ? 'var(--yellow)' : 'var(--muted)', borderColor: 'currentColor' }} />
                      <span><strong className="px-font text-[10px]">{i2.severity}</strong> · {i2.location}<br />{i2.problem}<br /><span className="text-muted">fix: {i2.fix}</span></span>
                    </li>
                  ))}
                </ul>
              )}
              <table className="w-full text-[12px]">
                <tbody>
                  {run.gates.map((g, j) => (
                    <tr key={j} className="border-b-2 border-dotted border-line">
                      <td className="py-2 pr-4 mono-kbd" style={g.status === 'fail' ? { color: 'var(--red)', borderColor: 'var(--red)' } : g.status === 'warn' ? { color: 'var(--yellow)', borderColor: 'var(--yellow)' } : undefined}>{g.name}</td>
                      <td className="py-2 pr-4" style={g.status === 'fail' ? { color: 'var(--red)' } : undefined}>{g.status}</td>
                      <td className="py-2 text-muted">{g.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          )}

          {tab === 'diff' && (
            <Panel title="Diff vs previous draft" id="diff-tab-h">
              {run.diff ? <pre className="max-h-[40rem] overflow-auto p-4 font-mono text-[11.5px] leading-[1.8]" style={{ border: '4px solid var(--line)' }}>{run.diff}</pre> : <p className="meta">No previous draft to diff against.</p>}
            </Panel>
          )}

          {tab === 'metadata' && (
            <Panel title="SEO metadata" id="meta-tab-h" className="max-w-3xl">
              {(() => {
                const seo = seoEdit ?? run.seo;
                if (!seo) return <p className="meta">No SEO package yet.</p>;
                const set = (patch: Partial<SeoView>) => setSeoEdit({ ...seo, ...patch });
                return (
                  <div className="space-y-5 text-[13px]">
                    <Field label="title"><input className={inputCls} value={seo.title} onChange={(e) => set({ title: e.target.value })} /></Field>
                    <Field label="description" hint={`${seo.description.length}/160`}><textarea className={taCls} rows={2} value={seo.description} onChange={(e) => set({ description: e.target.value })} /></Field>
                    <Field label="slug" hint={`→ apps/site/src/content/blog/${seo.slug}/index.md`}><input className={inputCls} value={seo.slug} onChange={(e) => set({ slug: e.target.value.toLowerCase() })} /></Field>
                    <div className="flex flex-wrap gap-8">
                      <Field label="tags (comma separated)"><input className={inputCls} style={{ width: '18rem' }} value={seo.tags.join(', ')} onChange={(e) => set({ tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean) })} /></Field>
                      <Field label="category">
                        <select className={inputCls} value={seo.category} onChange={(e) => set({ category: e.target.value })}>
                          {['news', 'guide', 'tutorial', 'opinion', 'tooling'].map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                      </Field>
                    </div>
                  </div>
                );
              })()}
            </Panel>
          )}

          {/* decision box */}
          <section className="px my-4 p-5 sm:p-6" aria-label="Decision" id="decision-h">
            <p className="px-font mb-4 text-[10px] text-muted">your decision</p>
            <Field label="comments (one per line)"><textarea className={taCls} rows={2} value={comments} onChange={(e) => setComments(e.target.value)} /></Field>
            <p className="mt-3 flex flex-wrap items-center gap-6 text-[12px]">
              <label className="flex items-center gap-2 text-muted">
                <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} style={{ width: '14px', height: '14px', accentColor: 'var(--red)' }} />
                force publish past {gatesBlocking ? 'blocking' : 'remaining'} gates
              </label>
            </p>
            {confirming && (
              <div className="mt-4 p-4 text-[12px]" style={{ border: '4px solid var(--accent)' }}>
                <p className="mb-3">Approving will <strong>publish now</strong>:</p>
                <ul className="space-y-1 font-mono text-[11px]">
                  <li>commit “content: {run.seo?.title}”</li>
                  <li>push origin main → benkicodes.pages.dev/blog/{run.seo?.slug}/</li>
                  <li>file apps/site/src/content/blog/{run.seo?.slug}/index.md</li>
                </ul>
                <p className="mt-4 flex gap-4">
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => sendReview('approve')} disabled={!!sending}>{sending ? 'publishing…' : 'publish now'}</button>
                  <button type="button" className="btn btn-sm" onClick={() => setConfirming(false)}>back</button>
                </p>
              </div>
            )}
            {!confirming && (
              <p className="mt-5 flex flex-wrap gap-4">
                <button type="button" className="btn btn-primary btn-sm" onClick={() => sendReview('approve')} disabled={!!sending}>approve → publish</button>
                <button type="button" className="btn btn-sm" onClick={() => sendReview('changes')} disabled={!!sending}>request changes</button>
                <button type="button" className="btn btn-sm text-bad" onClick={() => { setConfirming(false); if (window.confirm('Reject this run? The draft is kept but the run ends.')) sendReview('reject'); }} disabled={!!sending}>reject</button>
              </p>
            )}
          </section>
        </>
      )}

      {/* only while nothing is live: stream and poll are both off */}
      {run && !needStream && !run.pending && !terminal(st) && (
        <Panel title="Waiting" id="waiting-h"><p className="meta">Status “{st}” — nothing to decide right now. <ConfirmButton onConfirm={refresh} question="Refresh this run now?">refresh</ConfirmButton></p></Panel>
      )}

      {run && (
        <Panel title="Activity & calls" id="activity-h">
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
