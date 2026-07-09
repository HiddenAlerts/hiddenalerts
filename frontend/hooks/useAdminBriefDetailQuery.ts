'use client';

import { fetchAdminBriefDetail } from '@/lib/api/adminBriefs';
import { getAdminToken } from '@/lib/auth/adminSession';
import { useQuery } from '@tanstack/react-query';

export function adminBriefDetailQueryKey(briefId: string) {
  return ['admin-briefs', 'detail', briefId] as const;
}

export function useAdminBriefDetailQuery(briefId: string) {
  const token = getAdminToken();

  return useQuery({
    queryKey: adminBriefDetailQueryKey(briefId),
    queryFn: () => fetchAdminBriefDetail(briefId, token!),
    enabled: Boolean(briefId) && Boolean(token),
  });
}
