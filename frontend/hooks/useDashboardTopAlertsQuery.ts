'use client';

import { useAuth } from '@/contexts/AuthProvider';
import type { DashboardTopAlertItem } from '@/data/dashboardTopAlerts';
import { fetchTopAlerts } from '@/lib/api/alerts';
import { mapApiAlertToDashboardTopAlertItem } from '@/lib/mapApiAlertToDashboardTopAlert';
import { useQuery } from '@tanstack/react-query';

export function dashboardTopAlertsQueryKey() {
  return ['alerts', 'dashboard', 'top'] as const;
}

export function useDashboardTopAlertsQuery(options?: { enabled?: boolean }) {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();
  const enabled = (options?.enabled ?? true) && Boolean(token);

  return useQuery({
    queryKey: dashboardTopAlertsQueryKey(),
    queryFn: () => fetchTopAlerts(token!),
    select: data =>
      (data.alerts ?? [])
        .slice(0, 3)
        .map(
          (item, index): DashboardTopAlertItem =>
            mapApiAlertToDashboardTopAlertItem(item, index),
        ),
    staleTime: 60_000,
    enabled,
  });
}
