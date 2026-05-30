'use client';

import { useAuth } from '@/contexts/AuthProvider';
import { fetchAlertDetail } from '@/lib/api/alerts';
import { useQuery } from '@tanstack/react-query';

export function alertDetailQueryKey(alertId: string) {
  return ['alerts', 'detail', alertId] as const;
}

export function useAlertDetailQuery(alertId: string) {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();

  return useQuery({
    queryKey: alertDetailQueryKey(alertId),
    queryFn: () => fetchAlertDetail(alertId, token!),
    enabled: Boolean(alertId) && Boolean(token),
  });
}
