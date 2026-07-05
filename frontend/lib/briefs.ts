import { BRIEF_CATEGORY_FILTER_ALL } from '@/data/subscriberBriefs';
import type {
  BriefCountItem,
  BriefFilters,
  BriefRiskFilterValue,
  BriefRiskLabel,
  BriefSortValue,
  SubscriberBrief,
} from '@/types/briefs';

/** Maps a 0-100 risk score to its labelled band. */
export function riskScoreToLabel(score: number): BriefRiskLabel {
  if (score >= 80) return 'Critical';
  if (score >= 60) return 'High';
  if (score >= 40) return 'Medium';
  return 'Low';
}

function matchesRiskFilter(
  brief: SubscriberBrief,
  risk: BriefRiskFilterValue,
): boolean {
  if (risk === 'all') return true;
  const label = brief.riskLabel.toLowerCase();
  return label === risk;
}

function matchesSearch(brief: SubscriberBrief, search: string): boolean {
  const term = search.trim().toLowerCase();
  if (!term) return true;
  return (
    brief.title.toLowerCase().includes(term) ||
    brief.category.toLowerCase().includes(term) ||
    brief.summary.toLowerCase().includes(term) ||
    brief.coverageAreas.some(area => area.toLowerCase().includes(term))
  );
}

function compareBriefs(sort: BriefSortValue) {
  return (a: SubscriberBrief, b: SubscriberBrief): number => {
    switch (sort) {
      case 'oldest':
        return a.date.localeCompare(b.date);
      case 'risk-high':
        return b.riskScore - a.riskScore;
      case 'risk-low':
        return a.riskScore - b.riskScore;
      case 'newest':
      default:
        return b.date.localeCompare(a.date);
    }
  };
}

/** Applies search, category, and risk filters then sorts the result. */
export function filterAndSortBriefs(
  briefs: SubscriberBrief[],
  filters: BriefFilters,
): SubscriberBrief[] {
  return briefs
    .filter(
      brief =>
        matchesSearch(brief, filters.search) &&
        (filters.category === BRIEF_CATEGORY_FILTER_ALL ||
          brief.category === filters.category) &&
        matchesRiskFilter(brief, filters.risk),
    )
    .sort(compareBriefs(filters.sort));
}

export type BriefLibraryStats = {
  total: number;
  critical: number;
  high: number;
  updatedThisWeek: number;
};

export function getBriefStats(briefs: SubscriberBrief[]): BriefLibraryStats {
  return briefs.reduce<BriefLibraryStats>(
    (acc, brief) => {
      acc.total += 1;
      if (brief.riskLabel === 'Critical') acc.critical += 1;
      if (brief.riskLabel === 'High') acc.high += 1;
      if (brief.isNew) acc.updatedThisWeek += 1;
      return acc;
    },
    { total: 0, critical: 0, high: 0, updatedThisWeek: 0 },
  );
}

export function getFeaturedBrief(
  briefs: SubscriberBrief[],
): SubscriberBrief | undefined {
  return (
    briefs.find(brief => brief.featured) ??
    [...briefs].sort((a, b) => b.riskScore - a.riskScore)[0]
  );
}

/** Newest briefs, used for the "Recent Additions" strip. */
export function getRecentBriefs(
  briefs: SubscriberBrief[],
  limit = 3,
): SubscriberBrief[] {
  return [...briefs]
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, limit);
}

/** Unique primary categories with brief counts, sorted by count desc. */
export function getCategoryCounts(briefs: SubscriberBrief[]): BriefCountItem[] {
  const counts = new Map<string, number>();
  for (const brief of briefs) {
    counts.set(brief.category, (counts.get(brief.category) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

/** Coverage-area counts (briefs can appear in several areas), sorted desc. */
export function getCoverageCounts(briefs: SubscriberBrief[]): BriefCountItem[] {
  const counts = new Map<string, number>();
  for (const brief of briefs) {
    for (const area of brief.coverageAreas) {
      counts.set(area, (counts.get(area) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

export function formatBriefDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
