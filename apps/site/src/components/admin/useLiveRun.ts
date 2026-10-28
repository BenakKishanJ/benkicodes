// Live run state for course screens: SSE while the run works (first frame
// replaces — the server replays history), poll fallback, refresh on terminal.
// Same semantics as BlogReview's inline effect, extracted for course reuse.
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, streamRun, terminal, type StreamFrame } from './api';
import type { RunView } from './types';

export function useLiveRun(runId: string, onStatusChange: () => void) {
  const [run, setRun] = useState<RunView | null>(null);
  const [err, setErr] = useState<unknown>(null);
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

  useEffect(() => { setRun(null); refresh(); }, [runId, refresh]);

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
      () => { if (cancelled) return; onStatusRef.current(); refresh(); },
      () => {
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

  return { run, err, refresh, setErr };
}
