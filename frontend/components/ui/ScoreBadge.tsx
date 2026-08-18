import { cn } from '@/lib/utils';
import type { FC } from 'react';

export type ScoreBadgeProps = {
  /** Numeric score. `null` means the backend never scored this item. */
  score: number | null;
  riskLevel?: string | null;
  riskBand?: string | null;
  className?: string;
};

function hasNumericScore(score: number | null | undefined): score is number {
  return typeof score === 'number' && Number.isFinite(score);
}

/** Numeric score chip whose tone follows backend classification fields. */
function riskToneClasses(
  riskBand?: string | null,
  riskLevel?: string | null,
): string {
  const classification = (riskBand || riskLevel || '').trim().toLowerCase();
  if (classification === 'critical') {
    return 'bg-danger/20 text-danger border-danger/40';
  }
  if (classification === 'high') {
    return 'bg-danger-muted text-danger border-danger/30';
  }
  if (classification === 'medium') {
    return 'bg-warning-muted text-warning border-warning/30';
  }
  if (classification === 'low' || classification === 'below_60') {
    return 'bg-success-muted text-success border-success/30';
  }
  return 'border-border bg-surface-muted text-body';
}

export const ScoreBadge: FC<ScoreBadgeProps> = ({
  score,
  riskLevel,
  riskBand,
  className,
}) => {
  const scored = hasNumericScore(score);

  return (
    <span
      className={cn(
        'inline-flex h-8 min-w-12 items-center justify-center rounded-md border px-2 text-sm font-semibold',
        scored ? 'tabular-nums' : 'text-muted font-medium',
        scored
          ? riskToneClasses(riskBand, riskLevel)
          : 'border-border bg-surface-muted',
        className,
      )}
      title={scored ? undefined : 'Not scored'}
      aria-label={scored ? undefined : 'Not scored'}
    >
      {scored ? score : 'N/A'}
    </span>
  );
};
