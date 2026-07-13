'use client';

import type { AlertsRiskFilterValue } from '@/data/alertRiskFilterOptions';
import { ALERTS_PAGE_SIZE } from '@/lib/api/alerts';
import { cn } from '@/lib/utils';
import type { FC } from 'react';

function riskPhraseLabel(risk: AlertsRiskFilterValue): string {
  if (risk === 'all') return 'Critical & High';
  if (risk === 'critical') return 'Critical';
  return 'High';
}

function riskPhraseClass(risk: AlertsRiskFilterValue): string {
  if (risk === 'critical') return 'text-danger';
  if (risk === 'high') return 'text-warning';
  return 'text-foreground';
}

export type AlertsSummaryLineProps = {
  risk: AlertsRiskFilterValue;
  page: number;
  /** Total for this risk (and current category scope) from `/alerts/stats`. */
  filterTotal?: number;
  /** When known (from list `total` or stats-derived page count), show “Page X of Y”. */
  totalPages?: number;
  /** Trimmed `q` URL param — enables search-oriented summary copy. */
  activeSearchQuery?: string | null;
  className?: string;
};

export const AlertsSummaryLine: FC<AlertsSummaryLineProps> = ({
  risk,
  page,
  filterTotal,
  totalPages,
  activeSearchQuery,
  className,
}) => {
  const phrase = riskPhraseLabel(risk);
  const phraseClass = riskPhraseClass(risk);
  const hasTotal =
    typeof filterTotal === 'number' && Number.isFinite(filterTotal);
  const totalWord = hasTotal && filterTotal === 1 ? 'alert' : 'alerts';

  const searchHeadline =
    typeof activeSearchQuery === 'string' && activeSearchQuery.trim().length > 0
      ? activeSearchQuery.trim()
      : null;

  const rangeStart =
    hasTotal && filterTotal > 0
      ? (page - 1) * ALERTS_PAGE_SIZE + 1
      : 0;
  const rangeEnd =
    hasTotal && filterTotal > 0
      ? Math.min(page * ALERTS_PAGE_SIZE, filterTotal)
      : 0;

  return (
    <div
      className={cn(
        'text-body flex flex-col gap-1 text-sm sm:flex-row sm:items-baseline sm:justify-between',
        className,
      )}
    >
      <p>
        {searchHeadline ? (
          <>
            <span className="text-muted">Search </span>
            <span className="text-foreground font-semibold">
              &ldquo;{searchHeadline}&rdquo;
            </span>
            <span className="text-muted-foreground mx-1.5">•</span>
          </>
        ) : (
          <span className="text-muted">Showing </span>
        )}
        {hasTotal && filterTotal > 0 && !searchHeadline ? (
          <>
            <span className="text-foreground font-semibold tabular-nums">
              {rangeStart}
            </span>
            <span className="text-muted"> to </span>
            <span className="text-foreground font-semibold tabular-nums">
              {rangeEnd}
            </span>
            <span className="text-muted"> of </span>
            <span className="text-foreground font-semibold tabular-nums">
              {filterTotal}
            </span>
            <span className="text-muted"> — </span>
          </>
        ) : null}
        <span className={cn('font-semibold', phraseClass)}>{phrase}</span>
        <span className="text-muted">
          {risk === 'all' ? ' only' : ' alerts'}
        </span>
        <span className="text-muted-foreground mx-1.5">•</span>
        <span className="text-muted tabular-nums">
          Page {page}
          {typeof totalPages === 'number' && totalPages > 0 ? (
            <> of {totalPages}</>
          ) : null}
        </span>
      </p>
      <p className="text-muted shrink-0 text-right tabular-nums">
        <span className="text-muted">Total: </span>
        {hasTotal ? (
          <>
            <span className="text-foreground font-semibold">{filterTotal}</span>{' '}
            <span className="text-muted">{totalWord}</span>
          </>
        ) : (
          <span className="text-foreground font-semibold">—</span>
        )}
      </p>
    </div>
  );
};
