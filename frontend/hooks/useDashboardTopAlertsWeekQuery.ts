'use client';

import { useAuth } from '@/contexts/AuthProvider';
import type { DashboardTopAlertWeeklyItem } from '@/data/dashboardTopAlertsThisWeek';
import { fetchTopAlerts } from '@/lib/api/alerts';
import { mapApiAlertToDashboardTopAlertWeeklyItem } from '@/lib/mapApiAlertToDashboardTopAlertWeekly';
import { useQuery } from '@tanstack/react-query';

/** Number of weekly top alerts displayed on the dashboard. */
export const DASHBOARD_TOP_ALERTS_WEEK_LIMIT = 3;

export function dashboardTopAlertsWeekQueryKey() {
  return ['alerts', 'dashboard', 'top-week'] as const;
}

export function useDashboardTopAlertsWeekQuery(options?: {
  enabled?: boolean;
}) {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();
  const enabled = (options?.enabled ?? true) && Boolean(token);

  return useQuery({
    queryKey: dashboardTopAlertsWeekQueryKey(),
    queryFn: () => fetchTopAlerts(token!),
    select: data => {
      const now = Date.now();
      return (data.alerts ?? [])
        .slice(0, DASHBOARD_TOP_ALERTS_WEEK_LIMIT)
        .map(
          (item): DashboardTopAlertWeeklyItem =>
            mapApiAlertToDashboardTopAlertWeeklyItem(item, now),
        );
    },
    staleTime: 60_000,
    enabled,
  });
}
