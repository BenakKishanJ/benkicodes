// Client-only. Learning progress lives in localStorage; no accounts, no server.
const KEY = 'benki:progress:v1';
export const PASS_RATIO = 0.7;

export interface QuizResult { best: number; total: number; passed: boolean; at: string }
export type ProgressStore = { quizzes: Record<string, QuizResult> };

export function readProgress(): ProgressStore {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as ProgressStore;
  } catch { /* storage unavailable or corrupt */ }
  return { quizzes: {} };
}

export function saveQuizResult(quizId: string, score: number, total: number): void {
  try {
    const store = readProgress();
    const prev = store.quizzes[quizId];
    const best = prev ? Math.max(prev.best, score) : score;
    store.quizzes[quizId] = {
      best,
      total,
      passed: best / total >= PASS_RATIO,
      at: new Date().toISOString(),
    };
    localStorage.setItem(KEY, JSON.stringify(store));
    window.dispatchEvent(new CustomEvent('benki:progress'));
  } catch { /* ignore */ }
}

export function exportProgress(): string {
  return JSON.stringify(readProgress(), null, 2);
}

export function importProgress(json: string): boolean {
  try {
    const parsed = JSON.parse(json) as ProgressStore;
    if (!parsed || typeof parsed.quizzes !== 'object') return false;
    localStorage.setItem(KEY, JSON.stringify(parsed));
    window.dispatchEvent(new CustomEvent('benki:progress'));
    return true;
  } catch { return false; }
}
