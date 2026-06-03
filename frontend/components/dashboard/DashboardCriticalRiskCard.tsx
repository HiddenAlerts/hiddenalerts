import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

export type DashboardCriticalRiskTone = 'critical' | 'high';

const toneNumber: Record<DashboardCriticalRiskTone, string> = {
  critical: 'text-danger',
  high: 'text-warning',
};

const toneIconShell: Record<DashboardCriticalRiskTone, string> = {
  critical: 'bg-danger/15 text-danger border-danger/40',
  high: 'bg-warning/15 text-warning border-warning/40',
};

const toneRangeBadge: Record<DashboardCriticalRiskTone, string> = {
  critical: 'bg-danger/15 text-danger border-danger/35',
  high: 'bg-warning/15 text-warning border-warning/40',
};

const toneTrendText: Record<DashboardCriticalRiskTone, string> = {
  critical: 'text-danger',
  high: 'text-warning',
};

const toneBorderHover: Record<DashboardCriticalRiskTone, string> = {
  critical: 'hover:border-danger/45',
  high: 'hover:border-warning/45',
};

export type DashboardCriticalRiskCardProps = {
  label: string;
  /** Numeric range pill displayed next to the label, e.g. "80-100". */
  rangeLabel: string;
  /** Total count for this risk tier. */
  value: number;
  /** Short caption describing the urgency for this tier. */
  description: string;
  tone: DashboardCriticalRiskTone;
  icon: ReactNode;
  href: string;
  /** Number of new alerts since the user's previous login (optional). */
  newSinceLastLogin?: number;
  className?: string;
};

export const DashboardCriticalRiskCard: FC<DashboardCriticalRiskCardProps> = ({
  label,
  rangeLabel,
  value,
  description,
  tone,
  icon,
  href,
  newSinceLastLogin,
  className,
}) => {
  const showTrend =
    typeof newSinceLastLogin === 'number' && newSinceLastLogin > 0;

  return (
    <Link
      href={href}
      className={cn(
        'border-border bg-background-alt focus-visible:ring-primary-500/40 group relative flex flex-col gap-4 rounded-xl border p-5 transition-colors hover:bg-surface/30 focus-visible:ring-2 focus-visible:outline-none sm:p-6',
        toneBorderHover[tone],
        className,
      )}
    >
      <div className="flex items-start gap-4 sm:gap-5">
        <div
          className={cn(
            'flex size-12 shrink-0 items-center justify-center rounded-full border sm:size-14',
            toneIconShell[tone],
          )}
          aria-hidden
        >
          {icon}
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <p
            className={cn(
              'font-heading text-4xl font-bold tabular-nums leading-none sm:text-5xl',
              toneNumber[tone],
            )}
          >
            {value}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-foreground text-base font-semibold sm:text-lg">
              {label}
            </p>
            <span
              className={cn(
                'inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-medium tabular-nums',
                toneRangeBadge[tone],
              )}
            >
              {rangeLabel}
            </span>
          </div>
          <p className="text-muted text-sm">{description}</p>
        </div>
      </div>

      {showTrend ? (
        <div className="border-border-subtle border-t pt-3">
          <p
            className={cn(
              'inline-flex items-center gap-1.5 text-sm font-medium',
              toneTrendText[tone],
            )}
          >
            <ArrowUp className="size-4" aria-hidden />
            <span>
              {newSinceLastLogin} new since last login
            </span>
          </p>
        </div>
      ) : null}
    </Link>
  );
};
