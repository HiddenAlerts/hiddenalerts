'use client';

import { useAuth } from '@/contexts/AuthProvider';
import { ALERTS_PAGE_SIZE, fetchAlertsPage } from '@/lib/api/alerts';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

export function alertsListQueryKey(args: {
  page: number;
  risk: string;
  category: string;
}) {
  return ['alerts', 'list', args] as const;
}

export function useAlertsPageQuery(
  page: number,
  risk: string,
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
          ...(risk !== 'all' ? { risk_level: risk } : {}),
          ...(category !== 'all' ? { category } : {}),
        },
        token!,
      ),
    placeholderData: keepPreviousData,
    enabled: Boolean(token) && (options?.enabled ?? true),
  });
}
