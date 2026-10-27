// Tiny shared pieces for the admin suite (kept in one place, local styles only).
import { statusColor } from './api';
import type { ReactNode } from 'react';

export function Chip({ status, children }: { status?: string; children: ReactNode }) {
  const color = status ? statusColor(status) : 'var(--muted)';
  return (
    <span
      className="tag tag-plain"
      style={{ color, borderColor: color }}
      role="status"
    >
      {children}
    </span>
  );
}

export function ErrBox({ err, onRetry, label = 'retry' }: { err: unknown; onRetry?: () => void; label?: string }) {
  const msg = err instanceof Error ? err.message : String(err);
  return (
    <p role="alert" className="mx-2 my-3 flex flex-wrap items-center gap-4 p-3 text-[12px]"
       style={{ border: '2px solid var(--red)', color: 'var(--red)' }}>
      <span className="break-all">{msg}</span>
      {onRetry && <button type="button" className="copy-btn" onClick={onRetry}>{label}</button>}
    </p>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="px-font mb-2 block text-[10px] text-muted">{label}</span>
      {children}
      {hint && <span className="meta mt-1.5 block">{hint}</span>}
    </label>
  );
}

export const inputCls = 'w-full border-2 border-line bg-surface-2 px-3 py-2.5 text-[13px] leading-[1.7] text-fg outline-none focus:border-accent';
export const taCls = `${inputCls} font-mono resize-y`;

export function Panel({ title, right, children, id, className = '' }: {
  title?: ReactNode; right?: ReactNode; children: ReactNode; id?: string; className?: string;
}) {
  return (
    <section id={id} aria-labelledby={id} className={`px my-4 p-5 sm:p-6 ${className}`}>
      {title && (
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
          <h2 id={id} className="t-3">{title}</h2>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function ConfirmButton({ onConfirm, children, question, className = 'btn btn-sm', disabled }: {
  onConfirm: () => void; children: ReactNode; question: string; className?: string; disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      className={className}
      onClick={() => { if (window.confirm(question)) onConfirm(); }}
    >
      {children}
    </button>
  );
}
