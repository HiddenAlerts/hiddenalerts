import { cn } from '@/lib/utils';
import type { FC } from 'react';

/** Matches dashboard alert group tones and alerts risk tabs. */
export type RiskCountPillVariant = 'all' | 'high' | 'medium' | 'low';

const VARIANT_STYLES: Record<RiskCountPillVariant, string> = {
  all: 'bg-surface-muted text-muted-foreground',
  high: 'bg-danger-muted text-danger',
  medium: 'bg-warning-muted text-warning',
  low: 'bg-success-muted text-success',
};

const BASE =
  'inline-flex min-h-6 min-w-6 items-center justify-center rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums';

export type RiskCountPillProps = {
  variant: RiskCountPillVariant;
  count?: number;
  className?: string;
};

export const RiskCountPill: FC<RiskCountPillProps> = ({
  variant,
  count,
  className,
}) => {
  const label =
    typeof count === 'number' && Number.isFinite(count) ? String(count) : '—';
  return (
    <span className={cn(BASE, VARIANT_STYLES[variant], className)}>{label}</span>
  );
};
