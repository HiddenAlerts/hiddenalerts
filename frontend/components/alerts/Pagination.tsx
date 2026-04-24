'use client';

import { cn } from '@/lib/utils';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { FC } from 'react';

export type PaginationProps = {
  page: number;
  onPageChange: (page: number) => void;
  className?: string;
  /** When set, shows numbered pages (client-side full list). */
  totalPages?: number;
  /**
   * When `totalPages` is omitted, used for the Next control (server offset/limit).
   */
  hasNextPage?: boolean;
};

export const Pagination: FC<PaginationProps> = ({
  page,
  totalPages,
  hasNextPage,
  onPageChange,
  className,
}) => {
  const numbered = typeof totalPages === 'number' && totalPages > 0;
  const canPrev = page > 1;
  const canNext = numbered ? page < totalPages : Boolean(hasNextPage);

  const pages = numbered
    ? Array.from({ length: totalPages }, (_, i) => i + 1)
    : [];

  return (
    <nav
      className={cn(
        'border-border bg-background-alt flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2',
        className,
      )}
      aria-label="Pagination"
    >
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={!canPrev}
        className={cn(
          'text-body inline-flex h-9 items-center gap-1 rounded-md px-2 text-sm font-medium',
          'hover:bg-surface transition-colors disabled:pointer-events-none disabled:opacity-40',
        )}
      >
        <ChevronLeft className="size-4" aria-hidden />
        Previous
      </button>

      {numbered ? (
        <div className="flex flex-wrap items-center justify-center gap-1">
          {pages.map(n => {
            const active = n === page;
            return (
              <button
                key={n}
                type="button"
                onClick={() => onPageChange(n)}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'h-9 min-w-9 rounded-md px-2 text-sm font-medium transition-colors',
                  active
                    ? 'bg-primary-500 text-white'
                    : 'text-muted hover:bg-surface hover:text-foreground',
                )}
              >
                {n}
              </button>
            );
          })}
        </div>
      ) : (
        <p className="text-muted text-sm font-medium tabular-nums">
          Page {page}
        </p>
      )}

      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={!canNext}
        className={cn(
          'text-body inline-flex h-9 items-center gap-1 rounded-md px-2 text-sm font-medium',
          'hover:bg-surface transition-colors disabled:pointer-events-none disabled:opacity-40',
        )}
      >
        Next
        <ChevronRight className="size-4" aria-hidden />
      </button>
    </nav>
  );
};
