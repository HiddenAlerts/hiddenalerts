'use client';

import { useAuth } from '@/contexts/AuthProvider';
import {
  fetchSubscriberBriefsPage,
  SUBSCRIBER_BRIEFS_OVERVIEW_LIMIT,
} from '@/lib/api/subscriberBriefs';
import type { BriefLibraryStats } from '@/lib/briefs';
import type { BriefCountItem, SubscriberBrief } from '@/types/briefs';
import { useQuery } from '@tanstack/react-query';

export function subscriberBriefsOverviewQueryKey() {
  return ['subscriber-briefs', 'overview'] as const;
}

function countBy(
  briefs: SubscriberBrief[],
  pick: (brief: SubscriberBrief) => string[],
): BriefCountItem[] {
  const counts = new Map<string, number>();
  for (const brief of briefs) {
    for (const label of pick(brief)) {
      if (!label) continue;
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

export type SubscriberBriefsOverview = {
  stats: BriefLibraryStats;
  categories: BriefCountItem[];
  coverage: BriefCountItem[];
  recent: SubscriberBrief[];
};

/**
 * One bulk, unfiltered fetch (capped at the API's max page size) used to
 * derive category/coverage facet counts, risk stats, and the "recent
 * additions" strip — there's no dedicated stats/facets endpoint. Accurate as
 * long as the library stays under `SUBSCRIBER_BRIEFS_OVERVIEW_LIMIT` items;
 * the "Total" stat itself still comes from the endpoint's own `total` field.
 */
export function useSubscriberBriefsOverviewQuery() {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();

  return useQuery({
    queryKey: subscriberBriefsOverviewQueryKey(),
    queryFn: async (): Promise<SubscriberBriefsOverview> => {
      const { items, total } = await fetchSubscriberBriefsPage(
        { limit: SUBSCRIBER_BRIEFS_OVERVIEW_LIMIT, offset: 0 },
        token!,
      );
      return {
        stats: {
          total,
          critical: items.filter(b => b.riskLabel === 'Critical').length,
          high: items.filter(b => b.riskLabel === 'High').length,
        },
        categories: countBy(items, b => [b.category]),
        coverage: countBy(items, b => b.coverageAreas),
        recent: items.slice(0, 3),
      };
    },
    enabled: Boolean(token),
  });
}
