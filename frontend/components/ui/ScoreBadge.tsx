import { cn } from '@/lib/utils';
import type { FC } from 'react';

export type ScoreBadgeProps = {
  score: number;
  className?: string;
};

/**
 * Numeric risk score chip. Tone is derived from the score so callers don't
 * have to pass it in. Mirrors the CMS table style: a soft tinted background
 * with the score in a darker matching color.
 */
function scoreToneClasses(score: number): string {
  if (score >= 80) return 'bg-danger-muted text-danger border-danger/30';
  if (score >= 60) return 'bg-warning-muted text-warning border-warning/30';
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
