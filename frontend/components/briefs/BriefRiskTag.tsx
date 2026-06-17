import { cn } from '@/lib/utils';
import type { BriefRiskLabel } from '@/types/briefs';
import type { FC } from 'react';

const toneClasses: Record<BriefRiskLabel, string> = {
  Critical: 'bg-danger text-white',
  High: 'bg-warning text-secondary-900',
  Medium: 'bg-warning/80 text-secondary-900',
  Low: 'bg-success text-secondary-900',
};

export type BriefRiskTagProps = {
  riskLabel: BriefRiskLabel;
  className?: string;
};

/** Small solid "CRITICAL RISK" pill used on brief covers and the hero. */
export const BriefRiskTag: FC<BriefRiskTagProps> = ({
  riskLabel,
  className,
}) => (
  <span
    className={cn(
      'inline-flex items-center rounded-sm px-2 py-0.5 text-[0.65rem] font-bold tracking-wide uppercase',
      toneClasses[riskLabel],
      className,
    )}
  >
    {riskLabel} Risk
  </span>
);
