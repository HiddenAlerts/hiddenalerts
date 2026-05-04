import { cn } from '@/lib/utils';
import { ChevronRight } from 'lucide-react';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

export type DashboardRiskSummaryTone =
  | 'danger'
  | 'warning'
  | 'success'
  | 'info';

const toneRing: Record<DashboardRiskSummaryTone, string> = {
  danger: 'text-danger',
  warning: 'text-warning',
  success: 'text-success',
  info: 'text-info',
};

const toneIconBg: Record<DashboardRiskSummaryTone, string> = {
  danger: 'bg-danger-muted',
  warning: 'bg-warning-muted',
  success: 'bg-success-muted',
  info: 'bg-info-muted',
};

const toneAccent: Record<DashboardRiskSummaryTone, string> = {
  danger: 'border-t-danger hover:border-danger',
  warning: 'border-t-warning hover:border-warning',
  success: 'border-t-success hover:border-success',
  info: 'border-t-info hover:border-info',
};

export type DashboardRiskSummaryCardProps = {
  label: string;
  value: number;
  /** Percent of total, e.g. 25 for 25%. */
  percentOfTotal: number;
  tone: DashboardRiskSummaryTone;
  icon: ReactNode;
  href: string;
  className?: string;
};

export const DashboardRiskSummaryCard: FC<DashboardRiskSummaryCardProps> = ({
  label,
  value,
  percentOfTotal,
  tone,
  icon,
  href,
  className,
}) => (
  <Link
    href={href}
    className={cn(
      'border-border bg-background-alt group hover:border-primary-500/25 relative flex min-h-[5.5rem] cursor-pointer items-center gap-3 rounded-lg border border-t-[3px] py-3 pr-3 pl-3 shadow-xs transition-colors sm:gap-4 sm:py-3.5 sm:pr-4 sm:pl-4',
      'hover:bg-surface/35 focus-visible:ring-primary-500/40 focus-visible:ring-2 focus-visible:outline-none',
      toneAccent[tone],
      className,
    )}
  >
    <div
      className={cn(
        'flex size-10 shrink-0 items-center justify-center rounded-full sm:size-16',
        toneIconBg[tone],
        toneRing[tone],
      )}
    >
      {icon}
    </div>
    <div className="min-w-0 flex-1">
      <p
        className={cn(
          'font-heading text-2xl font-semibold tracking-tight tabular-nums sm:text-[1.65rem]',
          tone === 'danger' && 'text-danger',
          tone === 'warning' && 'text-warning',
          tone === 'success' && 'text-success',
          tone === 'info' && 'text-info',
        )}
      >
        {value}
      </p>
      <p className="text-foreground font-semibold tracking-tight">{label}</p>
      <p className="text-muted text-xs">{percentOfTotal}% of total</p>
    </div>
    <ChevronRight
      className="text-muted group-hover:text-foreground size-5 shrink-0 transition-colors"
      aria-hidden
    />
  </Link>
);
