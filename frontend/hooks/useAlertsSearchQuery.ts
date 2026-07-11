'use client';

import { useAuth } from '@/contexts/AuthProvider';
import { fetchAlertsSearch } from '@/lib/api/alerts';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

export function alertsSearchQueryKey(
  q: string,
  limits?: { limit?: number; groupLimit?: number },
) {
  return [
    'alerts',
    'search',
    q.trim(),
    limits?.limit ?? SEARCH_ALERTS_LIMIT,
    limits?.groupLimit ?? SEARCH_GROUP_LIMIT,
  ] as const;
}

const SEARCH_ALERTS_LIMIT = 100;
const SEARCH_GROUP_LIMIT = 50;

/** Lower limits for dashboard search (counts + top alerts only). */
export const DASHBOARD_SEARCH_ALERTS_LIMIT = 30;
export const DASHBOARD_SEARCH_GROUP_LIMIT = 20;

export function useAlertsSearchQuery(
  q: string,
  options?: {
    enabled?: boolean;
    limit?: number;
    groupLimit?: number;
  },
) {
  const trimmed = q.trim();
  const { getAccessToken } = useAuth();
  const token = getAccessToken();
  const enabled =
    (options?.enabled ?? true) && trimmed.length > 0 && Boolean(token);

  return useQuery({
    queryKey: alertsSearchQueryKey(trimmed, {
      limit: options?.limit,
      groupLimit: options?.groupLimit,
    }),
    queryFn: () =>
      fetchAlertsSearch(
        {
          q: trimmed,
          min_score: 0,
          limit: options?.limit ?? SEARCH_ALERTS_LIMIT,
          group_limit: options?.groupLimit ?? SEARCH_GROUP_LIMIT,
        },
        token!,
      ),
    placeholderData: keepPreviousData,
    enabled,
  });
}
