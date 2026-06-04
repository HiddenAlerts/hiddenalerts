import type { DashboardTopAlertWeeklyItem } from '@/data/dashboardTopAlertsThisWeek';
import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

import { DashboardSectionCard } from './DashboardSectionCard';
import { DashboardTopAlertRow } from './DashboardTopAlertRow';

export type DashboardTopAlertsThisWeekProps = {
  title?: string;
  subtitle?: string;
  alerts: DashboardTopAlertWeeklyItem[];
  viewAllHref?: string;
  viewAllLabel?: string;
  /** Optional replacement for the rows (loading/error/empty states). */
  bodyContent?: ReactNode;
  className?: string;
};

export const DashboardTopAlertsThisWeek: FC<
  DashboardTopAlertsThisWeekProps
> = ({
  title = 'Top Alerts This Week',
  subtitle = 'The highest priority threats based on risk score and recency.',
  alerts,
  viewAllHref,
  viewAllLabel,
  bodyContent,
  className,
}) => {
  const hasRows = !bodyContent && alerts.length > 0;

  return (
    <DashboardSectionCard
      title={title}
      subtitle={subtitle}
      viewAllHref={viewAllHref}
      viewAllLabel={viewAllLabel}
      headingId="dashboard-top-alerts-week-heading"
      className={className}
      bodyClassName={cn('mt-5', hasRows && 'space-y-3 lg:space-y-4')}
    >
      {bodyContent ? (
        bodyContent
      ) : alerts.length === 0 ? (
        <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
          No top alerts to display this week.
        </p>
      ) : (
        alerts.map(alert => (
          <DashboardTopAlertRow key={alert.id} alert={alert} />
        ))
      )}
    </DashboardSectionCard>
  );
};
