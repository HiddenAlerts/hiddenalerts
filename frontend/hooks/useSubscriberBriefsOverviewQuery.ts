'use client';

import { useAuth } from '@/contexts/AuthProvider';
import { BRIEF_CATEGORY_OPTIONS } from '@/data/briefCategories';
import {
  fetchSubscriberBriefsCount,
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
 * Stats and category counts are exact — the list endpoint's `total` is
 * accurate for any filter regardless of page size, so each is a cheap
 * `limit=1` count fetch run in parallel (one per known category, plus
 * critical/high/overall). "Coverage" (tags) and "recent additions" are
 * softer/exploratory, so those still come from one bulk sample (capped at
 * `SUBSCRIBER_BRIEFS_OVERVIEW_LIMIT`) rather than N more count queries.
 */
export function useSubscriberBriefsOverviewQuery() {
  const { getAccessToken } = useAuth();
  const token = getAccessToken();

  return useQuery({
    queryKey: subscriberBriefsOverviewQueryKey(),
    queryFn: async (): Promise<SubscriberBriefsOverview> => {
      const t = token!;

      const [total, critical, high, categoryCounts, sample] = await Promise.all([
        fetchSubscriberBriefsCount({}, t),
        fetchSubscriberBriefsCount({ risk_level: 'critical' }, t),
        fetchSubscriberBriefsCount({ risk_level: 'high' }, t),
        Promise.all(
          BRIEF_CATEGORY_OPTIONS.map(async option => ({
            label: option.label,
            count: await fetchSubscriberBriefsCount({ category: option.value }, t),
          })),
        ),
        fetchSubscriberBriefsPage(
          { limit: SUBSCRIBER_BRIEFS_OVERVIEW_LIMIT, offset: 0 },
          t,
        ),
      ]);

      return {
        stats: { total, critical, high },
        categories: categoryCounts
          .filter(c => c.count > 0)
          .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)),
        coverage: countBy(sample.items, b => b.coverageAreas),
        recent: sample.items.slice(0, 3),
      };
    },
    enabled: Boolean(token),
  });
}
