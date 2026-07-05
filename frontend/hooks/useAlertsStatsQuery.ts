'use client';

import { useAuth } from '@/contexts/AuthProvider';
import { fetchAlertsStats } from '@/lib/api/alerts';
import { useQuery } from '@tanstack/react-query';

export function alertsStatsQueryKey(categoryFilter: string) {
  return ['alerts', 'stats', categoryFilter] as const;
}

export function useAlertsStatsQuery(
  categoryFilter: string,
  options?: { enabled?: boolean },
) {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();
  const enabled = (options?.enabled ?? true) && Boolean(token);

  return useQuery({
    queryKey: alertsStatsQueryKey(categoryFilter),
    queryFn: () =>
      fetchAlertsStats(
        token!,
        categoryFilter !== 'all' ? { category: categoryFilter } : {},
      ),
    staleTime: 60_000,
    enabled,
  });
}
