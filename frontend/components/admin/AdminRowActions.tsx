'use client';

import { cn } from '@/lib/utils';
import { Pencil } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

export type AdminRowActionsProps = {
  /** Optional href for the edit icon. Renders a `Link` when provided. */
  editHref?: string;
  /** Optional callback for the edit icon. Used when no href is provided. */
  onEdit?: () => void;
  /** Label used for the edit action (used by screen readers). */
  editLabel?: string;
  className?: string;
};

const iconButtonClass =
  'text-muted hover:text-foreground hover:bg-surface inline-flex size-8 cursor-pointer items-center justify-center rounded-md transition-colors';

/**
 * Edit action icon shown in the last column of admin tables. Renders a
 * `Link` when `editHref` is provided, otherwise a button using `onEdit`.
 */
export const AdminRowActions: FC<AdminRowActionsProps> = ({
  editHref,
  onEdit,
  editLabel = 'Edit',
  className,
}) => (
  <div className={cn('flex items-center gap-1', className)}>
    {editHref ? (
      <Link href={editHref} className={iconButtonClass} aria-label={editLabel}>
        <Pencil className="size-4" aria-hidden />
      </Link>
    ) : (
      <button
        type="button"
        onClick={onEdit}
        className={iconButtonClass}
        aria-label={editLabel}
      >
        <Pencil className="size-4" aria-hidden />
      </button>
    )}
  </div>
);
