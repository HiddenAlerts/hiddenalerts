'use client';

import { useAuth } from '@/contexts/AuthProvider';
import type { DashboardTopAlertWeeklyItem } from '@/data/dashboardTopAlertsThisWeek';
import { fetchTopAlerts } from '@/lib/api/alerts';
import { mapApiAlertToDashboardTopAlertWeeklyItem } from '@/lib/mapApiAlertToDashboardTopAlertWeekly';
import { useQuery } from '@tanstack/react-query';

/** Display cap; `/alerts/top` currently returns at most 3 curated alerts. */
export const DASHBOARD_TOP_ALERTS_WEEK_LIMIT = 5;

function dedupeTopAlertsByIdAndTitle<T extends { id: number | string; title: string }>(
  alerts: T[],
): T[] {
  const seenIds = new Set<string>();
  const seenTitles = new Set<string>();
  const out: T[] = [];

  for (const alert of alerts) {
    const id = String(alert.id);
    const titleKey = alert.title.trim().toLowerCase().replace(/\s+/g, ' ');
    if (seenIds.has(id)) continue;
    if (titleKey && seenTitles.has(titleKey)) continue;
    seenIds.add(id);
    if (titleKey) seenTitles.add(titleKey);
    out.push(alert);
  }

  return out;
}

export function dashboardTopAlertsWeekQueryKey() {
  return ['alerts', 'dashboard', 'top', DASHBOARD_TOP_ALERTS_WEEK_LIMIT] as const;
}

/**
 * Top Alerts This Week from `GET /v1/subscriber/alerts/top`.
 */
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
      return dedupeTopAlertsByIdAndTitle(data.alerts ?? [])
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
