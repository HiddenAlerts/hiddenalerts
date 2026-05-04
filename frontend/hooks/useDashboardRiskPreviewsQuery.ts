'use client';

import { alertDisplayedAtIso } from '@/lib/alertDisplay';
import { fetchAlertsPage, mapApiAlertToAlertItem } from '@/lib/api/alerts';
import type { AlertItem } from '@/types/alert';
import { useQueries } from '@tanstack/react-query';
import { useMemo } from 'react';

export const DASHBOARD_RISK_PREVIEW_LIMIT = 3;

const PREVIEW_RISKS = ['high', 'medium', 'low'] as const;

export type DashboardPreviewRisk = (typeof PREVIEW_RISKS)[number];

export function dashboardRiskPreviewQueryKey(risk: DashboardPreviewRisk) {
  return ['alerts', 'dashboard', 'preview', risk] as const;
}

function sortPreviewAlerts(a: AlertItem, b: AlertItem): number {
  return alertDisplayedAtIso(b).localeCompare(alertDisplayedAtIso(a));
}

export function useDashboardRiskPreviewsQuery() {
  const results = useQueries({
    queries: PREVIEW_RISKS.map(risk => ({
      queryKey: dashboardRiskPreviewQueryKey(risk),
      queryFn: () =>
        fetchAlertsPage({
          limit: DASHBOARD_RISK_PREVIEW_LIMIT,
          offset: 0,
          risk_level: risk,
        }),
      staleTime: 60_000,
    })),
  });

  const [highQuery, mediumQuery, lowQuery] = results;

  const highAlerts = useMemo(() => {
    const items = (highQuery.data?.alerts ?? []).map(mapApiAlertToAlertItem);
    return [...items].sort(sortPreviewAlerts);
  }, [highQuery.data]);

  const mediumAlerts = useMemo(() => {
    const items = (mediumQuery.data?.alerts ?? []).map(mapApiAlertToAlertItem);
    return [...items].sort(sortPreviewAlerts);
  }, [mediumQuery.data]);

  const lowAlerts = useMemo(() => {
    const items = (lowQuery.data?.alerts ?? []).map(mapApiAlertToAlertItem);
    return [...items].sort(sortPreviewAlerts);
  }, [lowQuery.data]);

  const refetchAll = () =>
    Promise.all(results.map(q => q.refetch())).then(() => undefined);

  return {
    highQuery,
    mediumQuery,
    lowQuery,
    highAlerts,
    mediumAlerts,
    lowAlerts,
    refetchAll,
  };
}
