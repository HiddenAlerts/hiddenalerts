import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

export type AdminDetailFieldProps = {
  label: string;
  /** Optional helper next to the label, e.g. "(Public)" or "(Subscribers Only)". */
  hint?: string;
  /** Field value. Strings render as text; nodes pass through (e.g. tag chips). */
  children: ReactNode;
  /** When true, renders a multi-line block for paragraph-style values. */
  block?: boolean;
  className?: string;
};

/**
 * Read-only "field" used on detail pages — small label on top, value below,
 * styled to mirror the form layout so the two views feel related.
 */
export const AdminDetailField: FC<AdminDetailFieldProps> = ({
  label,
  hint,
  children,
  block = false,
  className,
}) => (
  <div className={cn('flex flex-col gap-1.5', className)}>
    <p className="text-foreground text-sm font-medium">
      {label}
      {hint ? <span className="text-muted ml-1 font-normal">{hint}</span> : null}
    </p>
    {block ? (
      <div className="text-body bg-surface/40 border-border min-h-[6rem] rounded-md border px-3 py-2.5 text-sm leading-relaxed whitespace-pre-line">
        {children || (
          <span className="text-muted italic">No content provided.</span>
        )}
      </div>
    ) : (
      <div className="text-body text-sm">{children || '—'}</div>
    )}
  </div>
);
