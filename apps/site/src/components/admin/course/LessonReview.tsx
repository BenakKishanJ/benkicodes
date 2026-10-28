// Lesson review: the lesson_review checkpoint (03-prd §7.6). Shows the rendered
// lesson, the part gates, the quiz and the reviewer's check — Ben approves,
// edits the markdown directly, sends it back for a lesson fix (max 2), or sends
// it back to the code (counts against the code-fix budget).
import { useState } from 'react';
import { Chip, Field, Panel, taCls } from '../ui';
import type { CourseRunView, LessonReviewDecision } from '../types';

function scoreColor(v: number): string | undefined {
  return v <= 2 ? 'var(--red)' : v === 3 ? 'var(--yellow)' : undefined;
}

export default function LessonReview({ course, pending, onSend, sending }: {
  runId: string;
  course: CourseRunView;
  pending: { type: string; note?: string; hard_fail?: string | null; round?: number } | null;
  onSend: (d: LessonReviewDecision, tag: string) => void;
  sending: string | null;
}) {
  const [tab, setTab] = useState<'lesson' | 'md' | 'quiz' | 'checks' | 'gates'>('lesson');
  const [md, setMd] = useState(course.lesson_md ?? '');
  const [comment, setComment] = useState('');
  const mdDirty = md.trim() !== (course.lesson_md ?? '').trim();

  const gates = course.gates ?? [];
  const check = course.check ?? null;
  const quiz = course.quiz ?? [];
  const fixes = course.lesson_fixes ?? 0;
  const codeFixes = course.code_fixes ?? 0;
  const edited = mdDirty ? md : null;

  return (
    <Panel title={`Part ${course.part_n} · lesson review`} id="lesson-review-h">
      <p className="meta mb-4">
        The lesson is drafted from the real commits. Gates already ran — anything
        {' '}<span style={{ color: 'var(--red)' }}>fail</span> blocks publishing;{' '}
        <span style={{ color: 'var(--yellow)' }}>warn</span> is your call.
      </p>

      {pending?.hard_fail && (
        <p className="meta mb-4" style={{ color: 'var(--red)' }}>hard gate failing: {pending.hard_fail}</p>
      )}
      {pending?.note && <p className="meta mb-4" style={{ color: 'var(--yellow)' }}>{pending.note}</p>}

      <div className="mb-4 flex flex-wrap gap-3">
        {([['lesson', 'preview'], ['md', 'markdown'], ['quiz', `quiz (${quiz.length})`],
           ['checks', 'reviewer'], ['gates', `gates (${gates.filter((g) => g.status !== 'pass').length}/${gates.length})`]] as const).map(
          ([k, label]) => (
            <button key={k} type="button" className={tab === k ? 'btn btn-sm btn-primary' : 'btn btn-sm'}
                    onClick={() => setTab(k)}>{label}</button>
          ))}
      </div>

      {tab === 'lesson' && (
        <article className="prose max-h-[36rem] overflow-auto" dangerouslySetInnerHTML={{ __html: course.lesson_html_rendered ?? '' }} />
      )}

      {tab === 'md' && (
        <>
          {mdDirty && <p className="meta mb-2" style={{ color: 'var(--yellow)' }}>edited — your text is authoritative and replaces the draft on approve</p>}
          <textarea className={taCls} rows={20} value={md} spellCheck={false} onChange={(e) => setMd(e.target.value)} aria-label="lesson markdown" />
        </>
      )}

      {tab === 'quiz' && (
        <ol className="space-y-4 text-[12px]">
          {quiz.map((q) => (
            <li key={q.id} className="px p-4">
              <p><span className="mono-kbd">{q.id}</span> <span className="text-fg">{q.question}</span>{q.type === 'multi' && <span className="text-muted"> · multi</span>}</p>
              <ul className="mt-2 space-y-1">
                {q.options.map((o) => (
                  <li key={o.id} style={q.correct.includes(o.id) ? { color: 'var(--green)' } : undefined}>
                    {o.id}) {o.text}{q.correct.includes(o.id) && ' ✓'}
                  </li>
                ))}
              </ul>
              {q.explanation && <p className="mt-2 text-muted">why: {q.explanation}</p>}
              {q.hint && <p className="mt-1 text-muted">hint: {q.hint}</p>}
            </li>
          ))}
        </ol>
      )}

      {tab === 'checks' && (
        <div className="text-[12px]">
          {check?.scores && (
            <p className="flex flex-wrap gap-4">
              {Object.entries(check.scores).map(([k, v]) => (
                <span key={k}><span className="px-font text-[10px] text-muted">{k}</span> <span style={{ color: scoreColor(v) }}>{v}/5</span></span>
              ))}
            </p>
          )}
          {(check?.issues ?? []).length > 0 && (
            <ul className="mt-4 space-y-2">
              {(check?.issues ?? []).map((i, j) => (
                <li key={j} style={i.severity === 'high' ? { color: 'var(--red)' } : undefined}>
                  <span className="mono-kbd">{i.severity}</span> <span className="text-muted">{i.location}:</span> {i.problem} <span className="text-muted">→ {i.fix}</span>
                </li>
              ))}
            </ul>
          )}
          {(check?.unsupported_claims ?? []).length > 0 && (
            <p className="mt-4" style={{ color: 'var(--yellow)' }}>unsupported: {(check?.unsupported_claims ?? []).join(' | ')}</p>
          )}
          {check?.summary_for_next && <p className="meta mt-4">summary for the next part: {check.summary_for_next}</p>}
          {!check && <p className="text-muted">no reviewer output yet</p>}
        </div>
      )}

      {tab === 'gates' && (
        <table className="w-full text-[12px]">
          <tbody>
            {gates.map((g, j) => (
              <tr key={j} className="border-b-2 border-dotted border-line">
                <td className="py-2 pr-4 mono-kbd" style={g.status === 'fail' ? { color: 'var(--red)', borderColor: 'var(--red)' } : g.status === 'warn' ? { color: 'var(--yellow)', borderColor: 'var(--yellow)' } : undefined}>{g.name}</td>
                <td className="py-2 pr-4" style={g.status === 'fail' ? { color: 'var(--red)' } : undefined}>{g.status}</td>
                <td className="py-2 text-muted">{g.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="mt-6"><Field label={`fix comment (lesson fixes used: ${fixes}/2 · code fixes used: ${codeFixes}/2)`}>
        <textarea className={taCls} rows={3} value={comment} spellCheck={false}
                  placeholder="e.g. step 2 teaches the wrong flag order — the code uses --priority first"
                  onChange={(e) => setComment(e.target.value)} />
      </Field></p>

      <p className="mt-4 flex flex-wrap gap-4">
        <button type="button" className="btn btn-primary btn-sm" disabled={sending !== null || !!pending?.hard_fail}
                onClick={() => onSend({ action: 'approve', edited_md: edited }, 'approve')}>
          {sending === 'approve' ? 'publishing…' : 'approve → publish part'}
        </button>
        <button type="button" className="btn btn-sm" disabled={sending !== null || !comment.trim() || fixes >= 2}
                onClick={() => onSend({ action: 'fix', comment }, 'lesson-fix')}>
          {sending === 'lesson-fix' ? 'sending…' : fixes >= 2 ? 'lesson fixes exhausted' : 'lesson fix'}
        </button>
        <button type="button" className="btn btn-sm" disabled={sending !== null || !comment.trim() || codeFixes >= 2}
                onClick={() => onSend({ action: 'back_to_code', comment }, 'back-to-code')}>
          {codeFixes >= 2 ? 'code budget exhausted' : 'back to code'}
        </button>
        {mdDirty && <Chip>markdown edited</Chip>}
      </p>
    </Panel>
  );
}
