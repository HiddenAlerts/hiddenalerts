'use client';

import { useAuth } from '@/contexts/AuthProvider';
import {
  fetchSubscriberBriefsPage,
  SUBSCRIBER_BRIEFS_PAGE_SIZE,
} from '@/lib/api/subscriberBriefs';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

export type SubscriberBriefsListArgs = {
  page: number;
  search: string;
  category: string;
  risk: string;
};

export function subscriberBriefsListQueryKey(args: SubscriberBriefsListArgs) {
  return ['subscriber-briefs', 'list', args] as const;
}

/** The paginated, server-filtered grid query. */
export function useSubscriberBriefsPageQuery(args: SubscriberBriefsListArgs) {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();
  const offset = (args.page - 1) * SUBSCRIBER_BRIEFS_PAGE_SIZE;

  return useQuery({
    queryKey: subscriberBriefsListQueryKey(args),
    queryFn: () =>
      fetchSubscriberBriefsPage(
        {
          limit: SUBSCRIBER_BRIEFS_PAGE_SIZE,
          offset,
          q: args.search.trim() || undefined,
          category: args.category !== 'all' ? args.category : undefined,
          risk_level: args.risk !== 'all' ? args.risk : undefined,
        },
        token!,
      ),
    placeholderData: keepPreviousData,
    enabled: Boolean(token),
  });
}
