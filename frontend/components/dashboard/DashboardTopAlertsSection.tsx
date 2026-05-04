import type {
  DashboardTopAlertItem,
  DashboardTopAlertRiskTone,
} from '@/data/dashboardTopAlerts';
import { cn } from '@/lib/utils';
import { ArrowRight, BellRing } from 'lucide-react';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

import { DashboardTopAlertCard } from './DashboardTopAlertCard';

const headerLinkTone: Record<
  DashboardTopAlertRiskTone,
  { className: string }
> = {
  high: {
    className: 'text-danger hover:text-danger-300',
  },
  medium: {
    className: 'text-warning hover:text-warning-300',
  },
  low: {
    className: 'text-success hover:text-success-300',
  },
};

export type DashboardTopAlertsSectionProps = {
  title: string;
  subtitle: string;
  viewAllHref: string;
  viewAllLabel: string;
  /** Accent for section border, header link, and score pills on cards. */
  riskTone?: DashboardTopAlertRiskTone;
  alerts: DashboardTopAlertItem[];
  /** Optional slot after subtitle (e.g. filters). */
  headerExtra?: ReactNode;
  className?: string;
};

const sectionBorderTone: Record<DashboardTopAlertRiskTone, string> = {
  high: 'border-danger/45',
  medium: 'border-warning/45',
  low: 'border-success/45',
};

const bellTone: Record<DashboardTopAlertRiskTone, string> = {
  high: 'text-danger',
  medium: 'text-warning',
  low: 'text-success',
};

export const DashboardTopAlertsSection: FC<DashboardTopAlertsSectionProps> = ({
  title,
  subtitle,
  viewAllHref,
  viewAllLabel,
  riskTone = 'high',
  alerts,
  headerExtra,
  className,
}) => {
  const linkTone = headerLinkTone[riskTone];

  return (
    <section
      className={cn(
        'bg-background-alt/40 rounded-xl border p-4 sm:p-5 lg:p-6',
        sectionBorderTone[riskTone],
        className,
      )}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="flex min-w-0 gap-3 sm:gap-4">
          <BellRing
            className={cn(
              'mt-0.5 size-7 shrink-0 sm:size-8',
              bellTone[riskTone],
            )}
            strokeWidth={1.75}
            aria-hidden
          />
          <div className="min-w-0 flex-1 space-y-1">
            <h2 className="font-heading text-foreground text-lg font-semibold tracking-tight sm:text-xl">
              {title}
            </h2>
            <p className="text-muted max-w-2xl text-sm leading-relaxed">
              {subtitle}
            </p>
            {headerExtra}
          </div>
        </div>
        <Link
          href={viewAllHref}
          className={cn(
            'inline-flex shrink-0 cursor-pointer items-center gap-1 text-sm font-semibold whitespace-nowrap sm:pt-1',
            linkTone.className,
          )}
        >
          {viewAllLabel}
          <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 lg:gap-4">
        {alerts.map(item => (
          <DashboardTopAlertCard
            key={item.id}
            alert={item}
            riskTone={riskTone}
          />
        ))}
      </div>
    </section>
  );
};
