// Run list: every run (blog + course) with a status chip; click to review, it polls while busy.
import { fmtTs } from '../api';
import type { RunItem } from '../types';
import { Chip } from '../ui';

export default function RunList({ runs, open, onDelete }: {
  runs: RunItem[];
  open: (id: string, mode?: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <section aria-label="Runs" className="px my-4 p-2 sm:p-3">
      {runs.length === 0 && <p className="meta m-4">No runs yet. Start one with “New blog” or “New course”.</p>}
      <ul>
        {runs.map((r) => (
          <li key={r.id} className="row group relative flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-4 text-[13px]">
            <Chip status={r.status}>{r.status}</Chip>
            {r.mode === 'course' && <span className="tag tag-plain">course</span>}
            <span className="min-w-0 flex-1 truncate">
              <span className="text-fg">{r.topic}</span>
              <span className="text-muted"> · {fmtTs(r.updated_at)}</span>
              {r.error && <span className="block font-mono text-[11px]" style={{ color: 'var(--red)' }}>{r.error.slice(0, 160)}</span>}
            </span>
            <button type="button" className="btn btn-sm" onClick={() => open(r.id, r.mode)}>open</button>
            <button type="button" className="icon-btn text-bad" aria-label={`delete run ${r.topic}`}
                    onClick={() => { if (window.confirm(`Delete run “${r.topic}”? Its draft history is lost.`)) onDelete(r.id); }}>×</button>
          </li>
        ))}
      </ul>
    </section>
  );
}
