'use client';

import { fetchAdminAlertDetail } from '@/lib/api/adminAlerts';
import { getAdminToken } from '@/lib/auth/adminSession';
import { useQuery } from '@tanstack/react-query';

export function adminAlertDetailQueryKey(alertId: string) {
  return ['admin-alerts', 'detail', alertId] as const;
}

export function useAdminAlertDetailQuery(alertId: string) {
  const token = getAdminToken();

  return useQuery({
    queryKey: adminAlertDetailQueryKey(alertId),
    queryFn: () => fetchAdminAlertDetail(alertId, token!),
    enabled: Boolean(alertId) && Boolean(token),
  });
}
