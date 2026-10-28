// Part workspace: the code_review checkpoint (03-prd §7.5). Shows the commits
// the pipeline just made on wip/part-N as per-commit diffs, lets Ben run the
// tests by hand (never automatic), edit files in the repo himself, then accept
// (optionally committing his manual edits) or ask for a fix (max 2 rounds).
import { useState } from 'react';
import { api, fmtTs } from '../api';
import { Chip, Field, inputCls, Panel, taCls } from '../ui';
import type { CodeReviewDecision, CourseRunView } from '../types';

const MAX_FIXES = 2;

export default function PartWorkspace({ runId, course, pending, onSend, sending, refresh }: {
  runId: string;
  course: CourseRunView;
  pending: { type: string; note?: string; code_fixes?: number; max_fixes?: number; changed_lines?: number } | null;
  onSend: (d: CodeReviewDecision, tag: string) => void;
  sending: string | null;
  refresh: () => Promise<unknown>;
}) {
  const commits = course.commits ?? [];
  const [tab, setTab] = useState<string>('all');
  const [diffs, setDiffs] = useState<Record<string, string>>({});
  const [loadingDiff, setLoadingDiff] = useState<string | null>(null);
  const [fix, setFix] = useState('');
  const [manualMsg, setManualMsg] = useState('');
  const [tests, setTests] = useState(course.tests ?? null);
  const [testing, setTesting] = useState(false);
  const [repoState, setRepoState] = useState<{ branch: string; clean: boolean; status: string; changed_lines: number; tags: string[] } | null>(null);

  const fixesUsed = pending?.code_fixes ?? course.code_fixes ?? 0;
  const maxFixes = pending?.max_fixes ?? MAX_FIXES;

  async function loadDiff(key: string) {
    setLoadingDiff(key);
    try {
      const r = await api.repoDiff(runId, key === 'all' ? 'all' : key);
      setDiffs((d) => ({ ...d, [key]: r.diff }));
    } finally {
      setLoadingDiff(null);
    }
  }

  async function runTests() {
    setTesting(true);
    try {
      const r = await api.repoTests(runId);
      setTests(r);
      await refresh();
    } finally {
      setTesting(false);
    }
  }

  async function refreshRepo() {
    const r = await api.repoRefresh(runId);
    setRepoState(r);
  }

  const tabKeys = [...commits.map((c) => c.sha), 'all'];
  const active = tabKeys.includes(tab) ? tab : 'all';

  return (
    <Panel title={`Part ${course.part_n} · code checkpoint`} id="part-workspace-h"
           right={pending?.changed_lines != null && <Chip>{pending.changed_lines} changed lines</Chip>}>
      <p className="meta mb-4">
        The pipeline committed this part's increments on <span className="font-mono text-accent">{course.repo?.path}</span>.
        Read the diffs, run the tests yourself, and either accept the code or ask for changes (a comment goes back to the coder).
        Edits you make in the repo are committed on accept.
      </p>

      {pending?.note && <p className="meta mb-4" style={{ color: 'var(--yellow)' }}>{pending.note}</p>}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        {commits.map((c) => (
          <button key={c.sha} type="button"
                  className={active === c.sha ? 'btn btn-sm btn-primary' : 'btn btn-sm'}
                  onClick={() => { setTab(c.sha); if (!diffs[c.sha]) void loadDiff(c.sha); }}>
            {c.sha.slice(0, 7)}
          </button>
        ))}
        <button type="button" className={active === 'all' ? 'btn btn-sm btn-primary' : 'btn btn-sm'}
                onClick={() => { setTab('all'); if (!diffs.all) void loadDiff('all'); }}>
          whole part
        </button>
        <span className="text-muted text-[12px]">{commits.length} commit(s)</span>
      </div>

      <pre className="max-h-96 overflow-auto p-3 font-mono text-[11px] leading-[1.5] bg-surface-2" aria-live="polite">
        {loadingDiff === active ? 'loading diff…'
          : diffs[active] ?? (active === 'all'
              ? `cumulative diff vs ${course.part_start_sha?.slice(0, 7) ?? 'part start'} — click “whole part” to load`
              : `${active.slice(0, 7)} — click the tab to load the diff`)}
      </pre>

      <div className="mt-4 flex flex-wrap items-start gap-4">
        <div className="flex-1 min-w-72">
          <p className="px-font mb-2 text-[10px] text-muted">tests (run by hand — never automatic)</p>
          {tests
            ? <p className="text-[12px]">
                <span style={{ color: tests.ok ? 'var(--green)' : 'var(--red)' }}>{tests.ok ? 'passed' : 'FAILED'}</span>
                <span className="text-muted"> · {tests.seconds}s · {fmtTs(tests.at)}</span>
                <details className="mt-2"><summary className="px-font text-[10px] text-muted">output</summary>
                  <pre className="mt-2 max-h-48 overflow-auto p-3 font-mono text-[11px]">{tests.output}</pre>
                </details>
              </p>
            : <p className="text-[12px] text-muted">not run yet this part</p>}
        </div>
        <div className="flex flex-col gap-2">
          <button type="button" className="btn btn-sm" onClick={runTests} disabled={testing}>
            {testing ? 'running…' : '▶ run tests'}
          </button>
          <button type="button" className="btn btn-sm" onClick={refreshRepo}>refresh repo state</button>
        </div>
      </div>

      {repoState && (
        <p className="meta mt-3 text-[12px]">
          branch <span className="font-mono">{repoState.branch}</span> · {repoState.clean ? 'clean' : <span style={{ color: 'var(--yellow)' }}>dirty (your edits will be committed on accept)</span>} · {repoState.changed_lines} changed lines · tags: {repoState.tags.join(', ') || 'none'}
          {!repoState.clean && <pre className="mt-2 max-h-40 overflow-auto p-3 font-mono text-[11px]">{repoState.status}</pre>}
        </p>
      )}

      <p className="mt-6"><Field label={`fix request${fixesUsed ? ` (${fixesUsed}/${maxFixes} used)` : ''} — one per line`}>
        <textarea className={taCls} rows={3} value={fix} spellCheck={false}
                  placeholder={'e.g. tests must cover the empty-list case\nsplit the CLI parsing into its own module'}
                  onChange={(e) => setFix(e.target.value)} />
      </Field></p>

      <p className="mt-4"><Field label="accept — commit message for your manual edits (optional)">
        <input className={inputCls} value={manualMsg} spellCheck={false}
               placeholder={`part-${course.part_n ?? ''}: manual adjustments`}
               onChange={(e) => setManualMsg(e.target.value)} />
      </Field></p>

      <p className="mt-4 flex flex-wrap gap-4">
        <button type="button" className="btn btn-primary btn-sm" disabled={sending !== null}
                onClick={() => onSend({ action: 'accept', commit_message: manualMsg.trim() || null }, 'accept')}>
          {sending === 'accept' ? 'accepting…' : 'accept code → write the lesson'}
        </button>
        <button type="button" className="btn btn-sm" disabled={sending !== null || !fix.trim() || fixesUsed >= maxFixes}
                onClick={() => onSend({ action: 'fix', comment: fix.split('\n').map((x) => x.trim()).filter(Boolean).join('\n') }, 'fix')}>
          {sending === 'fix' ? 'sending…' : fixesUsed >= maxFixes ? 'fix budget exhausted' : 'ask for changes'}
        </button>
      </p>
    </Panel>
  );
}
