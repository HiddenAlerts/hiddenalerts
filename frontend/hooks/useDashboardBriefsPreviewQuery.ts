'use client';

import { useAuth } from '@/contexts/AuthProvider';
import { fetchSubscriberBriefsPage } from '@/lib/api/subscriberBriefs';
import { useQuery } from '@tanstack/react-query';

/** Brief cards on the subscriber dashboard (three per row). */
export const DASHBOARD_BRIEFS_PREVIEW_LIMIT = 3;

export function dashboardBriefsPreviewQueryKey() {
  return [
    'subscriber-briefs',
    'dashboard',
    'preview',
    DASHBOARD_BRIEFS_PREVIEW_LIMIT,
  ] as const;
}

export function useDashboardBriefsPreviewQuery(options?: { enabled?: boolean }) {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();
  const enabled = (options?.enabled ?? true) && Boolean(token);

  return useQuery({
    queryKey: dashboardBriefsPreviewQueryKey(),
    queryFn: () =>
      fetchSubscriberBriefsPage(
        { limit: DASHBOARD_BRIEFS_PREVIEW_LIMIT, offset: 0 },
        token!,
      ),
    staleTime: 60_000,
    enabled,
  });
}
