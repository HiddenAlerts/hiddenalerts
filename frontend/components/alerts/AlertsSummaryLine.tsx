'use client';

import type { AlertsRiskFilterValue } from '@/data/alertRiskFilterOptions';
import { cn } from '@/lib/utils';
import type { FC } from 'react';

function riskPhraseLabel(risk: AlertsRiskFilterValue): string {
  if (risk === 'all') return 'All';
  if (risk === 'high') return 'High Risk';
  if (risk === 'medium') return 'Medium Risk';
  return 'Low Risk';
}

function riskPhraseClass(risk: AlertsRiskFilterValue): string {
  if (risk === 'high') return 'text-danger';
  if (risk === 'medium') return 'text-warning';
  if (risk === 'low') return 'text-success';
  return 'text-foreground';
}

export type AlertsSummaryLineProps = {
  risk: AlertsRiskFilterValue;
  page: number;
  /** Total for this risk (and current category scope) from `/alerts/stats`. */
  filterTotal?: number;
  className?: string;
};

export const AlertsSummaryLine: FC<AlertsSummaryLineProps> = ({
  risk,
  page,
  filterTotal,
  className,
}) => {
  const phrase = riskPhraseLabel(risk);
  const phraseClass = riskPhraseClass(risk);
  const hasTotal =
    typeof filterTotal === 'number' && Number.isFinite(filterTotal);
  const totalWord =
    hasTotal && filterTotal === 1 ? 'alert' : 'alerts';

  return (
    <div
      className={cn(
        'text-body flex flex-col gap-1 text-sm sm:flex-row sm:items-baseline sm:justify-between',
        className,
      )}
    >
      <p>
        <span className="text-muted">Showing </span>
        <span className={cn('font-semibold', phraseClass)}>{phrase}</span>
        <span className="text-muted"> alerts</span>
        <span className="text-muted-foreground mx-1.5">•</span>
        <span className="text-muted tabular-nums">Page {page}</span>
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
