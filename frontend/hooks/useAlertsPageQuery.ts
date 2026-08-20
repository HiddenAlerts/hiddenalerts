'use client';

import { useAuth } from '@/contexts/AuthProvider';
import {
  subscriberAlertsApiRiskBand,
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
 * Subscriber browse list — forwards the selected risk band to the API
 * (`risk_band=critical|high`). "All" omits the param so the published
 * Critical+High pool is returned.
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
  const riskBand = subscriberAlertsApiRiskBand(risk);

  return useQuery({
    queryKey: alertsListQueryKey({ page, risk, category }),
    queryFn: () =>
      fetchAlertsPage(
        {
          limit: ALERTS_PAGE_SIZE,
          offset,
          ...(riskBand ? { risk_band: riskBand } : {}),
          ...(category !== 'all' ? { category } : {}),
        },
        token!,
      ),
    placeholderData: keepPreviousData,
    enabled: Boolean(token) && (options?.enabled ?? true),
  });
}
