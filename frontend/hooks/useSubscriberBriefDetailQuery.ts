'use client';

import { useAuth } from '@/contexts/AuthProvider';
import { fetchSubscriberBriefBySlug } from '@/lib/api/subscriberBriefs';
import { useQuery } from '@tanstack/react-query';

export function subscriberBriefDetailQueryKey(slug: string) {
  return ['subscriber-briefs', 'detail', slug] as const;
}

export function useSubscriberBriefDetailQuery(slug: string) {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();

  return useQuery({
    queryKey: subscriberBriefDetailQueryKey(slug),
    queryFn: () => fetchSubscriberBriefBySlug(slug, token!),
    enabled: Boolean(slug) && Boolean(token),
  });
}
