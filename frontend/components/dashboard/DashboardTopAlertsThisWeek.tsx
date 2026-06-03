import type { DashboardTopAlertWeeklyItem } from '@/data/dashboardTopAlertsThisWeek';
import { cn } from '@/lib/utils';
import type { FC } from 'react';

import { DashboardSectionCard } from './DashboardSectionCard';
import { DashboardTopAlertRow } from './DashboardTopAlertRow';

export type DashboardTopAlertsThisWeekProps = {
  title?: string;
  subtitle?: string;
  alerts: DashboardTopAlertWeeklyItem[];
  viewAllHref?: string;
  viewAllLabel?: string;
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
  className,
}) => (
  <DashboardSectionCard
    title={title}
    subtitle={subtitle}
    viewAllHref={viewAllHref}
    viewAllLabel={viewAllLabel}
    headingId="dashboard-top-alerts-week-heading"
    className={className}
    bodyClassName={cn(
      alerts.length === 0 ? 'mt-5' : 'mt-5 space-y-3 lg:space-y-4',
    )}
  >
    {alerts.length === 0 ? (
      <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
        No top alerts to display this week.
      </p>
    ) : (
      alerts.map(alert => <DashboardTopAlertRow key={alert.id} alert={alert} />)
    )}
  </DashboardSectionCard>
);
