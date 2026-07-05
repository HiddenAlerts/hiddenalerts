'use client';

import { cn } from '@/lib/utils';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { FC } from 'react';

export type AdminPaginationProps = {
  /** 1-based current page. */
  page: number;
  pageSize: number;
  totalItems: number;
  /** Label used in the summary line, e.g. "alerts". */
  itemLabel: string;
  onPageChange: (page: number) => void;
  className?: string;
};

/**
 * Numeric pagination control with a "Showing X to Y of Z" summary.
 *
 * Renders compact page buttons with ellipses when there are many pages.
 */
export const AdminPagination: FC<AdminPaginationProps> = ({
  page,
  pageSize,
  totalItems,
  itemLabel,
  onPageChange,
  className,
}) => {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const start = totalItems === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(totalItems, page * pageSize);

  const pageItems = buildPageItems(page, totalPages);

  const canPrev = page > 1;
  const canNext = page < totalPages;

  return (
    <nav
      className={cn(
        'flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
      aria-label="Pagination"
    >
      <p className="text-muted text-sm">
        Showing {start} to {end} of {totalItems} {itemLabel}
      </p>

      <div className="flex flex-wrap items-center gap-1">
        <PageButton
          onClick={() => onPageChange(page - 1)}
          disabled={!canPrev}
          aria-label="Previous page"
        >
          <ChevronLeft className="size-4" aria-hidden />
        </PageButton>

        {pageItems.map((item, index) =>
          item === 'ellipsis' ? (
            <span
              key={`ellipsis-${index}`}
              className="text-muted px-2 text-sm select-none"
              aria-hidden
            >
              …
            </span>
          ) : (
            <PageButton
              key={item}
              onClick={() => onPageChange(item)}
              active={item === page}
              aria-label={`Page ${item}`}
              aria-current={item === page ? 'page' : undefined}
            >
              {item}
            </PageButton>
          ),
        )}

        <PageButton
          onClick={() => onPageChange(page + 1)}
          disabled={!canNext}
          aria-label="Next page"
        >
          <ChevronRight className="size-4" aria-hidden />
        </PageButton>
      </div>
    </nav>
  );
};

type PageButtonProps = {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  active?: boolean;
  'aria-label'?: string;
  'aria-current'?: 'page' | undefined;
};

const PageButton: FC<PageButtonProps> = ({
  children,
  onClick,
  disabled,
  active,
  ...rest
}) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    className={cn(
      'border-border inline-flex h-9 min-w-9 cursor-pointer items-center justify-center rounded-md border px-2 text-sm font-medium transition-colors',
      'hover:bg-surface',
      'disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40',
      active
        ? 'bg-primary-500 border-primary-500 text-white hover:bg-primary-600'
        : 'text-body bg-background-alt',
    )}
    {...rest}
  >
    {children}
  </button>
);

/**
 * Builds a compact page list with optional ellipses for ranges, e.g.:
 *   [1, 2, 3, 4, '...', 10]
 */
function buildPageItems(
  current: number,
  total: number,
): Array<number | 'ellipsis'> {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const items: Array<number | 'ellipsis'> = [];
  const showLeftEllipsis = current > 4;
  const showRightEllipsis = current < total - 3;

  items.push(1);
  if (showLeftEllipsis) items.push('ellipsis');

  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  for (let i = start; i <= end; i++) {
    items.push(i);
  }

  if (showRightEllipsis) items.push('ellipsis');
  items.push(total);

  return items;
}
