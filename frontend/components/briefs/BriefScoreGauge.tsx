import { formatBriefRiskScore, riskScoreToLabel } from '@/lib/briefs';
import { cn } from '@/lib/utils';
import type { BriefRiskLabel } from '@/types/briefs';
import type { FC } from 'react';

const TONE_CLASSES: Record<BriefRiskLabel, { text: string; bar: string }> = {
  Critical: { text: 'text-danger', bar: 'bg-danger' },
  High: { text: 'text-warning', bar: 'bg-warning' },
  Medium: { text: 'text-warning', bar: 'bg-warning' },
  Low: { text: 'text-success', bar: 'bg-success' },
};

export type BriefScoreGaugeProps = {
  score: number;
  className?: string;
};

/** "RISK SCORE 94/100" box with a colored horizontal progress bar. */
export const BriefScoreGauge: FC<BriefScoreGaugeProps> = ({
  score,
  className,
}) => {
  const hasScore =
    typeof score === 'number' && Number.isFinite(score) && score > 0;
  const tone = TONE_CLASSES[riskScoreToLabel(hasScore ? score : 0)];
  const pct = hasScore ? Math.max(0, Math.min(100, score)) : 0;
  const display = formatBriefRiskScore(score);
  const [main, denom] = display.includes('/')
    ? (display.split('/') as [string, string])
    : ([display, null] as const);

  return (
    <div
      className={cn(
        'border-border bg-background-alt w-full max-w-56 shrink-0 rounded-lg border px-5 py-4',
        className,
      )}
    >
      <p className="text-muted text-xs font-semibold tracking-wide uppercase">
        Risk Score
      </p>
      <p className="mt-1 flex items-baseline gap-1">
        <span className={cn('text-3xl font-bold tabular-nums', tone.text)}>
          {main}
        </span>
        {denom ? <span className="text-muted text-sm">/{denom}</span> : null}
      </p>
      <div className="bg-surface-muted mt-3 h-1.5 w-full overflow-hidden rounded-full">
        <div
          className={cn('h-full rounded-full', tone.bar)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
};
