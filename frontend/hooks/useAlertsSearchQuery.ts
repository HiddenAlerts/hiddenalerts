'use client';

import { fetchAlertsSearch } from '@/lib/api/alerts';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

export function alertsSearchQueryKey(q: string) {
  return ['alerts', 'search', q.trim()] as const;
}

const SEARCH_ALERTS_LIMIT = 100;
const SEARCH_GROUP_LIMIT = 50;

export function useAlertsSearchQuery(q: string, options?: { enabled?: boolean }) {
  const trimmed = q.trim();
  const enabled = (options?.enabled ?? true) && trimmed.length > 0;

  return useQuery({
    queryKey: alertsSearchQueryKey(trimmed),
    queryFn: () =>
      fetchAlertsSearch({
        q: trimmed,
        min_score: 0,
        limit: SEARCH_ALERTS_LIMIT,
        group_limit: SEARCH_GROUP_LIMIT,
      }),
    placeholderData: keepPreviousData,
    enabled,
  });
}
