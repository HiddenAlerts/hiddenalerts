'use client';

import { useAuth } from '@/contexts/AuthProvider';
import { fetchAlertsPage, mapApiAlertToAlertItem } from '@/lib/api/alerts';
import { useQueries } from '@tanstack/react-query';
import { useMemo } from 'react';

export const DASHBOARD_RISK_PREVIEW_LIMIT = 3;

/** Canonical subscriber `risk_band` values for dashboard previews. */
const PREVIEW_RISKS = ['critical', 'high', 'medium', 'below_60'] as const;

export type DashboardPreviewRisk = (typeof PREVIEW_RISKS)[number];

export function dashboardRiskPreviewQueryKey(risk: DashboardPreviewRisk) {
  return ['alerts', 'dashboard', 'preview', risk] as const;
}

export function useDashboardRiskPreviewsQuery(options?: {
  enabled?: boolean;
}) {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();
  const enabled = (options?.enabled ?? true) && Boolean(token);

  const results = useQueries({
    queries: PREVIEW_RISKS.map(risk => ({
      queryKey: dashboardRiskPreviewQueryKey(risk),
      queryFn: () =>
        fetchAlertsPage(
          {
            limit: DASHBOARD_RISK_PREVIEW_LIMIT,
            offset: 0,
            risk_band: risk,
          },
          token!,
        ),
      staleTime: 60_000,
      enabled,
    })),
  });

  const [criticalQuery, highQuery, mediumQuery, below60Query] = results;

  // Preserve backend Published order (published_at DESC …); do not re-sort by source date.
  const criticalAlerts = useMemo(
    () => (criticalQuery.data?.alerts ?? []).map(mapApiAlertToAlertItem),
    [criticalQuery.data],
  );

  const highAlerts = useMemo(
    () => (highQuery.data?.alerts ?? []).map(mapApiAlertToAlertItem),
    [highQuery.data],
  );

  const mediumAlerts = useMemo(
    () => (mediumQuery.data?.alerts ?? []).map(mapApiAlertToAlertItem),
    [mediumQuery.data],
  );

  const below60Alerts = useMemo(
    () => (below60Query.data?.alerts ?? []).map(mapApiAlertToAlertItem),
    [below60Query.data],
  );

  const refetchAll = () =>
    Promise.all(results.map(q => q.refetch())).then(() => undefined);

  return {
    criticalQuery,
    highQuery,
    mediumQuery,
    below60Query,
    criticalAlerts,
    highAlerts,
    mediumAlerts,
    below60Alerts,
    refetchAll,
  };
}
