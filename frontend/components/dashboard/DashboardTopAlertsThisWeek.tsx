import type { DashboardTopAlertWeeklyItem } from '@/data/dashboardTopAlertsThisWeek';
import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

import { DashboardSectionCard } from './DashboardSectionCard';
import { DashboardTopAlertRow } from './DashboardTopAlertRow';

export type DashboardTopAlertsThisWeekProps = {
  title?: string;
  subtitle?: string;
  alerts: DashboardTopAlertWeeklyItem[];
  /** API fallback notice (7-day window empty); omit or null when not in fallback. */
  fallbackMessage?: string | null;
  viewAllHref?: string;
  viewAllLabel?: string;
  /** Optional replacement for the rows (loading/error/empty states). */
  bodyContent?: ReactNode;
  className?: string;
};

export const DashboardTopAlertsThisWeek: FC<
  DashboardTopAlertsThisWeekProps
> = ({
  title = 'Latest Critical & High Alerts',
  subtitle = 'Newest Critical and High-Risk threats — updated continuously.',
  alerts,
  fallbackMessage,
  viewAllHref,
  viewAllLabel,
  bodyContent,
  className,
}) => {
  const notice = fallbackMessage?.trim() || null;
  const hasRows = !bodyContent && alerts.length > 0;

  return (
    <DashboardSectionCard
      title={title}
      subtitle={subtitle}
      viewAllHref={viewAllHref}
      viewAllLabel={viewAllLabel}
      headingId="dashboard-latest-critical-high-alerts-heading"
      className={className}
      bodyClassName={cn('mt-5', hasRows && 'space-y-3 lg:space-y-4')}
    >
      {bodyContent ? (
        bodyContent
      ) : alerts.length === 0 ? (
        <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
          No Critical or High-Risk alerts to display right now.
        </p>
      ) : (
        <>
          {notice ? (
            <p role="status" className="text-muted text-sm leading-relaxed">
              {notice}
            </p>
          ) : null}
          {alerts.map(alert => (
            <DashboardTopAlertRow key={alert.id} alert={alert} />
          ))}
        </>
      )}
    </DashboardSectionCard>
  );
};
