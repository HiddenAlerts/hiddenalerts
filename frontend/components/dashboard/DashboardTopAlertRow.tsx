import type {
  DashboardTopAlertWeeklyIcon,
  DashboardTopAlertWeeklyItem,
  DashboardTopAlertWeeklyRiskTone,
} from '@/data/dashboardTopAlertsThisWeek';
import { cn } from '@/lib/utils';
import {
  Calendar,
  ChevronRight,
  Landmark,
  Package,
  Phone,
  ShieldAlert,
} from 'lucide-react';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

const iconForType: Record<DashboardTopAlertWeeklyIcon, ReactNode> = {
  phone: <Phone className="size-5" strokeWidth={1.75} aria-hidden />,
  package: <Package className="size-5" strokeWidth={1.75} aria-hidden />,
  landmark: <Landmark className="size-5" strokeWidth={1.75} aria-hidden />,
  shield: <ShieldAlert className="size-5" strokeWidth={1.75} aria-hidden />,
};

const scoreToneStyles: Record<
  DashboardTopAlertWeeklyRiskTone,
  { score: string; label: string; box: string }
> = {
  critical: {
    score: 'text-danger',
    label: 'text-danger',
    box: 'border-danger/40 bg-danger/5',
  },
  high: {
    score: 'text-warning',
    label: 'text-warning',
    box: 'border-warning/40 bg-warning/5',
  },
  medium: {
    score: 'text-warning',
    label: 'text-warning',
    box: 'border-warning/40 bg-warning/5',
  },
};

const iconShellTone: Record<DashboardTopAlertWeeklyRiskTone, string> = {
  critical: 'bg-danger/15 text-danger',
  high: 'bg-warning/15 text-warning',
  medium: 'bg-warning/15 text-warning',
};

function formatOccurredAt(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { date: iso, time: '' };
  const date = d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const time = d.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC',
  });
  return { date, time: `${time} UTC` };
}

export type DashboardTopAlertRowProps = {
  alert: DashboardTopAlertWeeklyItem;
  className?: string;
};

export const DashboardTopAlertRow: FC<DashboardTopAlertRowProps> = ({
  alert,
  className,
}) => {
  const scoreStyle = scoreToneStyles[alert.riskTone];
  const { date, time } = formatOccurredAt(alert.occurredAtIso);

  return (
    <Link
      href={alert.href}
      className={cn(
        'border-border bg-background hover:border-primary-500/40 focus-visible:ring-primary-500/40 group block rounded-lg border p-4 transition-colors focus-visible:ring-2 focus-visible:outline-none sm:p-5',
        className,
      )}
      aria-label={`Open alert: ${alert.title}, risk score ${alert.riskScore} out of 100, ${alert.riskLabel}`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:gap-5">
        <div
          className={cn(
            'flex w-full shrink-0 flex-col items-center justify-center gap-0.5 rounded-md border px-2 py-2.5 leading-tight sm:w-[5.25rem]',
            scoreStyle.box,
          )}
        >
          <span
            className={cn(
              'font-heading text-2xl font-bold tabular-nums sm:text-[1.75rem]',
              scoreStyle.score,
            )}
          >
            {alert.riskScore}
          </span>
          <span
            className={cn(
              'text-center text-xs font-semibold tracking-tight',
              scoreStyle.label,
            )}
          >
            {alert.riskLabel}
          </span>
          <span className="text-muted text-[0.65rem] tabular-nums">
            {alert.riskRange}
          </span>
        </div>

        <div className="flex min-w-0 flex-1 items-start gap-3 sm:gap-4">
          <span
            className={cn(
              'mt-0.5 hidden size-10 shrink-0 items-center justify-center rounded-full sm:inline-flex',
              iconShellTone[alert.riskTone],
            )}
            aria-hidden
          >
            {iconForType[alert.iconType]}
          </span>

          <div className="min-w-0 flex-1 space-y-1.5">
            <h3 className="text-foreground line-clamp-2 text-base font-semibold leading-snug">
              {alert.title}
            </h3>
            {alert.tags.length > 0 ? (
              <p className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-sm leading-snug">
                {alert.tags.map((tag, i) => (
                  <span
                    key={`${tag}-${i}`}
                    className="text-info inline-flex items-center font-medium"
                  >
                    {i > 0 ? (
                      <span
                        className="text-muted-foreground/55 mr-1.5"
                        aria-hidden
                      >
                        •
                      </span>
                    ) : null}
                    {tag}
                  </span>
                ))}
              </p>
            ) : null}
            {alert.headline ? (
              <p className="text-foreground text-sm font-semibold leading-snug">
                {alert.headline}
              </p>
            ) : null}
            <p className="text-muted line-clamp-3 text-sm leading-relaxed">
              {alert.description}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 flex-row items-center justify-between gap-3 sm:flex-col sm:items-end sm:gap-2">
          {alert.isNew ? (
            <span className="bg-danger inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold text-white">
              NEW
            </span>
          ) : (
            <span aria-hidden className="hidden sm:block sm:h-5" />
          )}
          <div className="text-muted inline-flex items-center gap-1.5 text-xs leading-snug sm:flex-col sm:items-end sm:gap-0">
            <Calendar
              className="text-muted-foreground size-3.5 shrink-0 sm:hidden"
              strokeWidth={1.5}
              aria-hidden
            />
            <span className="text-foreground sm:text-right">{date}</span>
            <span className="sm:text-right">{time}</span>
          </div>
          <ChevronRight
            className="text-danger group-hover:text-danger-300 size-5 shrink-0 transition-colors"
            aria-hidden
          />
        </div>
      </div>
    </Link>
  );
};
