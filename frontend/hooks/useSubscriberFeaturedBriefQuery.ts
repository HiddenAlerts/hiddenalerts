'use client';

import { useAuth } from '@/contexts/AuthProvider';
import { fetchFeaturedSubscriberBrief } from '@/lib/api/subscriberBriefs';
import { useQuery } from '@tanstack/react-query';

export function subscriberFeaturedBriefQueryKey() {
  return ['subscriber-briefs', 'featured'] as const;
}

export function useSubscriberFeaturedBriefQuery() {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();

  return useQuery({
    queryKey: subscriberFeaturedBriefQueryKey(),
    queryFn: () => fetchFeaturedSubscriberBrief(token!),
    enabled: Boolean(token),
  });
}
