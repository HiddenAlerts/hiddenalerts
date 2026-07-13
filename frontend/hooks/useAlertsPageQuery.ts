'use client';

import { useAuth } from '@/contexts/AuthProvider';
import {
  SUBSCRIBER_ALERTS_API_RISK_LEVEL,
  type AlertsRiskFilterValue,
} from '@/data/alertRiskFilterOptions';
import { ALERTS_PAGE_SIZE, fetchAlertsPage } from '@/lib/api/alerts';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

export function alertsListQueryKey(args: {
  page: number;
  risk: string;
  category: string;
}) {
  return ['alerts', 'list', args] as const;
}

/**
 * Subscriber browse list — always requests the Critical+High API pool
 * (`risk_level=high`). Critical vs High pills are applied client-side from
 * `risk_band` (backend list has no `critical` risk_level).
 */
export function useAlertsPageQuery(
  page: number,
  risk: AlertsRiskFilterValue | string,
  category: string,
  options?: { enabled?: boolean },
) {
  const offset = (page - 1) * ALERTS_PAGE_SIZE;
  const { getAccessToken } = useAuth();
  const token = getAccessToken();

  return useQuery({
    queryKey: alertsListQueryKey({ page, risk, category }),
    queryFn: () =>
      fetchAlertsPage(
        {
          limit: ALERTS_PAGE_SIZE,
          offset,
          risk_level: SUBSCRIBER_ALERTS_API_RISK_LEVEL,
          ...(category !== 'all' ? { category } : {}),
        },
        token!,
      ),
    placeholderData: keepPreviousData,
    enabled: Boolean(token) && (options?.enabled ?? true),
  });
}
