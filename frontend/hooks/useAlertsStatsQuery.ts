'use client';

import { fetchAlertsStats } from '@/lib/api/alerts';
import { useQuery } from '@tanstack/react-query';

export function alertsStatsQueryKey(categoryFilter: string) {
  return ['alerts', 'stats', categoryFilter] as const;
}

export function useAlertsStatsQuery(categoryFilter: string) {
  return useQuery({
    queryKey: alertsStatsQueryKey(categoryFilter),
    queryFn: () =>
      fetchAlertsStats(
        categoryFilter !== 'all' ? { category: categoryFilter } : {},
      ),
    staleTime: 60_000,
  });
}
