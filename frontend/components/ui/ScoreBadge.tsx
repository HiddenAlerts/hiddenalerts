import {
  ALERT_SCORE_THRESHOLDS,
} from '@/lib/alertDisplay';
import { cn } from '@/lib/utils';
import type { FC } from 'react';

export type ScoreBadgeProps = {
  score: number;
  className?: string;
};

/**
 * Numeric risk score chip. Tone follows admin CMS thresholds:
 * Critical ≥81, High ≥71, Medium ≥61.
 */
function scoreToneClasses(score: number): string {
  if (score >= ALERT_SCORE_THRESHOLDS.critical) {
    return 'bg-danger/20 text-danger border-danger/40';
  }
  if (score >= ALERT_SCORE_THRESHOLDS.high) {
    return 'bg-danger-muted text-danger border-danger/30';
  }
  if (score >= ALERT_SCORE_THRESHOLDS.medium) {
    return 'bg-warning-muted text-warning border-warning/30';
  }
  return 'bg-success-muted text-success border-success/30';
}

export const ScoreBadge: FC<ScoreBadgeProps> = ({ score, className }) => (
  <span
    className={cn(
      'inline-flex h-8 min-w-12 items-center justify-center rounded-md border px-2 text-sm font-semibold tabular-nums',
      scoreToneClasses(score),
      className,
    )}
  >
    {score}
  </span>
);
