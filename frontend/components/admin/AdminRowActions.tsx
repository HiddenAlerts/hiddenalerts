'use client';

import { cn } from '@/lib/utils';
import { MoreHorizontal, Pencil } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

export type AdminRowActionsProps = {
  /** Optional href for the edit icon. Renders a `Link` when provided. */
  editHref?: string;
  /** Optional callback for the edit icon. Used when no href is provided. */
  onEdit?: () => void;
  /** Optional callback for the "more" overflow icon. */
  onMore?: () => void;
  /** Label used for the edit action (used by screen readers). */
  editLabel?: string;
  /** Label used for the more-options action (used by screen readers). */
  moreLabel?: string;
  className?: string;
};

const iconButtonClass =
  'text-muted hover:text-foreground hover:bg-surface inline-flex size-8 cursor-pointer items-center justify-center rounded-md transition-colors';

/**
 * Pair of action icons typically shown in the last column of admin tables.
 * The edit icon can be either a Link (when `editHref` is set) or a button.
 */
export const AdminRowActions: FC<AdminRowActionsProps> = ({
  editHref,
  onEdit,
  onMore,
  editLabel = 'Edit',
  moreLabel = 'More options',
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
    <button
      type="button"
      onClick={onMore}
      className={iconButtonClass}
      aria-label={moreLabel}
    >
      <MoreHorizontal className="size-4" aria-hidden />
    </button>
  </div>
);
