'use client';

import { fetchAlertDetail } from '@/lib/api/alerts';
import { useQuery } from '@tanstack/react-query';

export function alertDetailQueryKey(alertId: string) {
  return ['alerts', 'detail', alertId] as const;
}

export function useAlertDetailQuery(alertId: string) {
  return useQuery({
    queryKey: alertDetailQueryKey(alertId),
    queryFn: () => fetchAlertDetail(alertId),
    enabled: Boolean(alertId),
  });
}
