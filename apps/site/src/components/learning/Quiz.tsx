import { useEffect, useMemo, useRef, useState } from 'react';
import { PASS_RATIO, saveQuizResult } from '../../lib/progress';
import { pixelConfetti } from '../../scripts/pixelfx';

export interface QuizOption { id: string; text: string }
export interface QuizQuestion {
  id: string;
  question: string;
  type: 'single' | 'multi';
  options: QuizOption[];
  correct: string[];
  explanation: string;
  difficulty?: string;
  hint?: string;
}
interface Props { quizId: string; questions: QuizQuestion[] }

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((x) => b.includes(x));

const Check = () => (
  <svg width="12" height="12" viewBox="0 0 8 8" fill="currentColor" shapeRendering="crispEdges" aria-hidden="true">
    <rect x="6" y="1" width="2" height="1" /><rect x="5" y="2" width="2" height="1" /><rect x="0" y="3" width="2" height="1" />
    <rect x="4" y="3" width="2" height="1" /><rect x="1" y="4" width="4" height="1" /><rect x="2" y="5" width="2" height="1" />
  </svg>
);

export default function Quiz({ quizId, questions }: Props) {
  const [attempt, setAttempt] = useState(0);
  const [qs, setQs] = useState<QuizQuestion[]>(questions); // unshuffled on server to avoid hydration mismatch
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [submitted, setSubmitted] = useState(false);
  const [hints, setHints] = useState<Record<string, boolean>>({});
  const submitRef = useRef<HTMLButtonElement>(null);

  // Shuffle on the client only (first mount, and on every retry).
  useEffect(() => {
    setQs(shuffle(questions).map((q) => ({ ...q, options: shuffle(q.options) })));
    setAnswers({});
    setSubmitted(false);
    setHints({});
  }, [attempt, questions]);

  const score = useMemo(
    () => qs.filter((q) => sameSet(answers[q.id] ?? [], q.correct)).length,
    [qs, answers],
  );
  const answered = qs.filter((q) => (answers[q.id] ?? []).length > 0).length;
  const allAnswered = answered === qs.length;
  const passed = score / qs.length >= PASS_RATIO;

  function toggle(q: QuizQuestion, optId: string) {
    if (submitted) return;
    setAnswers((prev) => {
      const cur = prev[q.id] ?? [];
      if (q.type === 'single') return { ...prev, [q.id]: [optId] };
      return { ...prev, [q.id]: cur.includes(optId) ? cur.filter((x) => x !== optId) : [...cur, optId] };
    });
  }

  function submit() {
    setSubmitted(true);
    saveQuizResult(quizId, score, qs.length);
    if (passed) {
      const r = submitRef.current?.getBoundingClientRect();
      pixelConfetti(r ? r.left + r.width / 2 : undefined, r ? r.top : undefined);
    }
  }

  return (
    <section aria-labelledby={`quiz-${quizId}`} className="px p-6 sm:p-10">
      <div className="flex flex-wrap items-baseline justify-between gap-3 border-b-2 border-line pb-6">
        <h2 id={`quiz-${quizId}`} className="t-2">quiz</h2>
        <p className="meta">{qs.length} questions · pass at {Math.round(PASS_RATIO * 100)}% · {answered}/{qs.length} answered</p>
      </div>

      <div className="mt-10 space-y-14">
        {qs.map((q, idx) => {
          const chosen = answers[q.id] ?? [];
          const correct = sameSet(chosen, q.correct);
          return (
            <fieldset key={q.id}>
              <legend className="mb-6 flex gap-4">
                <span className="px-font text-[11px] leading-[2] text-accent">Q{idx + 1}</span>
                <span className="text-[15px] font-semibold leading-relaxed">
                  {q.question}
                  {q.type === 'multi' && <span className="meta ml-2 font-normal">(select all that apply)</span>}
                </span>
              </legend>
              <div>
                {q.options.map((o) => {
                  const isChosen = chosen.includes(o.id);
                  const isRight = q.correct.includes(o.id);
                  const result = submitted ? (isRight ? 'right' : isChosen ? 'wrong' : undefined) : undefined;
                  return (
                    <label
                      key={o.id}
                      className="opt text-[14px]"
                      data-chosen={isChosen || undefined}
                      data-result={result}
                      data-locked={submitted || undefined}
                      data-multi={q.type === 'multi' || undefined}
                    >
                      <input
                        type={q.type === 'single' ? 'radio' : 'checkbox'}
                        name={`${quizId}-${q.id}`}
                        checked={isChosen}
                        disabled={submitted}
                        onChange={() => toggle(q, o.id)}
                      />
                      <span className="mark">{(isChosen || (submitted && isRight)) && <Check />}</span>
                      <span>
                        {o.text}
                        {submitted && isRight && <span className="ml-3 text-[11px]" style={{ color: 'var(--green)' }}>[correct]</span>}
                        {submitted && isChosen && !isRight && <span className="ml-3 text-[11px]" style={{ color: 'var(--red)' }}>[not this one]</span>}
                      </span>
                    </label>
                  );
                })}
              </div>
              {!submitted && q.hint && (
                <div className="mt-2">
                  <button type="button" className="text-[12px] text-muted underline decoration-dashed underline-offset-4 hover:text-accent" onClick={() => setHints((h) => ({ ...h, [q.id]: !h[q.id] }))}>
                    {hints[q.id] ? 'hide hint' : 'show hint'}
                  </button>
                  {hints[q.id] && <p className="mt-2 text-[13px] text-muted">{q.hint}</p>}
                </div>
              )}
              {submitted && (
                <p className="mt-4 bg-surface-2 p-4 text-[13px] leading-relaxed" aria-live="polite" style={{ borderLeft: `6px solid ${correct ? 'var(--green)' : 'var(--red)'}` }}>
                  <strong>{correct ? 'Correct. ' : 'Not quite. '}</strong>
                  {q.explanation}
                </p>
              )}
            </fieldset>
          );
        })}
      </div>

      <div className="mt-14 flex flex-wrap items-center gap-5 border-t-2 border-line pt-8">
        {!submitted ? (
          <>
            <button ref={submitRef} type="button" className="btn btn-primary" disabled={!allAnswered} onClick={submit}>check answers</button>
            {!allAnswered && <span className="meta">answer every question to continue</span>}
          </>
        ) : (
          <>
            <p className="px-font text-[1.25rem]" role="status" aria-live="polite" style={{ color: passed ? 'var(--green)' : 'var(--yellow)' }}>
              {score}/{qs.length}
            </p>
            <p className="text-[13px]">{passed ? 'Module complete. Nice work.' : 'Review the lesson, then retry.'}</p>
            <button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>retry</button>
          </>
        )}
      </div>
    </section>
  );
}
