'use client';

import { cn } from '@/lib/utils';
import type { FC } from 'react';

export type AlertsSummaryLineProps = {
  /** e.g. "High Risk" or "All" */
  riskLabel: string;
  page: number;
  resultCount: number;
  className?: string;
};

export const AlertsSummaryLine: FC<AlertsSummaryLineProps> = ({
  riskLabel,
  page,
  resultCount,
  className,
}) => (
  <div
    className={cn(
      'text-body flex flex-col gap-1 text-sm sm:flex-row sm:items-baseline sm:justify-between',
      className,
    )}
  >
    <p>
      <span className="text-muted">Showing </span>
      <span className="text-foreground font-semibold">{riskLabel}</span>
      <span className="text-muted"> alerts</span>
      <span className="text-muted-foreground mx-1.5">•</span>
      <span className="text-muted tabular-nums">Page {page}</span>
    </p>
    <p className="text-muted shrink-0 text-right tabular-nums">
      <span className="text-muted">Total (this page): </span>
      <span className="text-foreground font-semibold">{resultCount}</span>{' '}
      {resultCount === 1 ? 'alert' : 'alerts'}
    </p>
  </div>
);
