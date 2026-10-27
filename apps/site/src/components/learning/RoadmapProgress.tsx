import { useEffect, useState } from 'react';
import { readProgress, exportProgress, importProgress, type ProgressStore } from '../../lib/progress';
import { SPRITES, spriteRects } from '../../lib/sprites';

const LOCK = spriteRects(SPRITES.lock);

interface Mod { slug: string; title: string; order: number; minutes: number }
interface Planned { slug: string; title: string; minutes: number }
interface Props { roadmap: string; modules: Mod[]; planned?: Planned[] }

export default function RoadmapProgress({ roadmap, modules, planned = [] }: Props) {
  const [store, setStore] = useState<ProgressStore>({ quizzes: {} });

  useEffect(() => {
    const sync = () => setStore(readProgress());
    sync();
    window.addEventListener('benki:progress', sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener('benki:progress', sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  const stateOf = (slug: string) => {
    const r = store.quizzes[`${roadmap}/${slug}`];
    return r ? (r.passed ? 'done' : 'attempted') : 'todo';
  };
  const done = modules.filter((m) => stateOf(m.slug) === 'done').length;
  const pct = modules.length ? Math.round((done / modules.length) * 100) : 0;

  function download() {
    const blob = new Blob([exportProgress()], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'benki-progress.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }
  function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    f.text().then((t) => { if (!importProgress(t)) alert('That file is not a valid progress export.'); });
  }

  return (
    <div>
      <div className="mb-14 max-w-xl">
        <div className="mb-3 flex justify-between text-[12px] text-muted">
          <span>progress</span>
          <span>{done}/{modules.length} modules · {pct}%</span>
        </div>
        <div className="seg-bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Roadmap progress">
        {modules.map((m, i) => <i key={m.slug} className={stateOf(m.slug) === 'done' ? 'on' : ''} style={{ ['--i' as string]: i }} />)}
      </div>
      {planned.length > 0 && (
        <p className="mt-3 text-[12px] text-muted">{planned.length} more part{planned.length !== 1 ? 's' : ''} planned</p>
      )}
    </div>

      <ol className="track">
        {modules.map((m, i) => {
          const s = stateOf(m.slug);
          const r = store.quizzes[`${roadmap}/${m.slug}`];
          return (
            <li key={m.slug} data-state={s}>
              <span className="node" aria-hidden="true">{s === 'done' ? '✓' : i + 1}</span>
              <a href={`/roadmaps/${roadmap}/${m.slug}/`} className="group block">
                <span className="t-3 group-hover:text-accent">{m.title}</span>
                <span className="mt-2 block text-[12px] text-muted">
                  ~{m.minutes} min
                  {s === 'done' && <span style={{ color: 'var(--green)' }}> · passed {r.best}/{r.total}</span>}
                  {s === 'attempted' && <span style={{ color: 'var(--yellow)' }}> · best {r.best}/{r.total}, retry to pass</span>}
                  {s === 'todo' && <span> · not started</span>}
                </span>
              </a>
            </li>
          );
        })}

        {planned.map((p) => (
          <li key={p.slug} data-state="planned">
            <span className="node" aria-hidden="true">
              <svg width={14} height={16} viewBox="0 0 7 8" fill="currentColor" shape-rendering="crispEdges" dangerouslySetInnerHTML={{ __html: LOCK }} />
            </span>
            <span className="block">
              <span className="t-3">{p.title}</span>
              <span className="mt-2 block text-[12px] text-muted">~{p.minutes} min · <span className="soon">coming soon</span></span>
            </span>
          </li>
        ))}
      </ol>

      <div className="mt-14 flex flex-wrap gap-4">
        <button type="button" className="btn btn-sm" onClick={download}>export progress</button>
        <label className="btn btn-sm">
          import progress
          <input type="file" accept="application/json" className="sr-only" onChange={upload} />
        </label>
      </div>
    </div>
  );
}
