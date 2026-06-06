'use client';

import { Pagination } from '@/components/alerts/Pagination';
import { SUBSCRIBER_MOCK_BRIEFS } from '@/data/subscriberBriefs';
import {
  filterAndSortBriefs,
  getBriefStats,
  getCategoryCounts,
  getCoverageCounts,
  getFeaturedBrief,
  getRecentBriefs,
} from '@/lib/briefs';
import type {
  BriefFilters,
  BriefRiskFilterValue,
  BriefSortValue,
  SubscriberBrief,
} from '@/types/briefs';
import { type FC, useMemo, useState } from 'react';

import { BriefsGrid } from './BriefsGrid';
import { BriefsLibraryHeader } from './BriefsLibraryHeader';
import { BriefsLibrarySidebar } from './BriefsLibrarySidebar';
import { BriefsStatsRow } from './BriefsStatsRow';
import { FeaturedBriefCard } from './FeaturedBriefCard';
import { RecentAdditions } from './RecentAdditions';

const PAGE_SIZE = 8;

const DEFAULT_FILTERS: BriefFilters = {
  search: '',
  category: 'all',
  risk: 'all',
  sort: 'newest',
};

export type BriefsLibraryScreenProps = {
  /** Defaults to the bundled mock library; injectable for tests/future API. */
  briefs?: SubscriberBrief[];
};

export const BriefsLibraryScreen: FC<BriefsLibraryScreenProps> = ({
  briefs = SUBSCRIBER_MOCK_BRIEFS,
}) => {
  const [filters, setFilters] = useState<BriefFilters>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);

  const stats = useMemo(() => getBriefStats(briefs), [briefs]);
  const featured = useMemo(() => getFeaturedBrief(briefs), [briefs]);
  const recent = useMemo(() => getRecentBriefs(briefs, 3), [briefs]);
  const categories = useMemo(() => getCategoryCounts(briefs), [briefs]);
  const coverage = useMemo(() => getCoverageCounts(briefs), [briefs]);

  const categoryOptions = useMemo(
    () => [
      { value: 'all', label: 'All Categories' },
      ...categories.map(category => ({
        value: category.label,
        label: category.label,
      })),
    ],
    [categories],
  );

  const filteredBriefs = useMemo(
    () => filterAndSortBriefs(briefs, filters),
    [briefs, filters],
  );

  const hasActiveFilters =
    filters.search.trim() !== '' ||
    filters.category !== 'all' ||
    filters.risk !== 'all' ||
    filters.sort !== 'newest';

  const totalPages = Math.max(1, Math.ceil(filteredBriefs.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pagedBriefs = useMemo(
    () =>
      filteredBriefs.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE),
    [filteredBriefs, safePage],
  );

  const showHighlights = !hasActiveFilters && safePage === 1;

  function updateFilters(patch: Partial<BriefFilters>) {
    setFilters(prev => ({ ...prev, ...patch }));
    setPage(1);
  }

  const total = filteredBriefs.length;
  const firstShown = total === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const lastShown = Math.min(safePage * PAGE_SIZE, total);

  return (
    <div className="space-y-6">
      <BriefsLibraryHeader
        filters={filters}
        categoryOptions={categoryOptions}
        onSearchChange={value => updateFilters({ search: value })}
        onCategoryChange={value => updateFilters({ category: value })}
        onRiskChange={(value: BriefRiskFilterValue) =>
          updateFilters({ risk: value })
        }
        onSortChange={(value: BriefSortValue) => updateFilters({ sort: value })}
        onReset={() => {
          setFilters(DEFAULT_FILTERS);
          setPage(1);
        }}
        hasActiveFilters={hasActiveFilters}
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem] xl:gap-6">
        <div className="min-w-0 space-y-5">
          <BriefsStatsRow stats={stats} />

          {showHighlights && featured ? (
            <FeaturedBriefCard brief={featured} />
          ) : null}

          {showHighlights ? (
            <RecentAdditions briefs={recent} viewAllHref="/briefs" />
          ) : null}

          <div className="space-y-3">
            <p className="text-muted text-sm" role="status" aria-live="polite">
              Showing{' '}
              <span className="text-foreground font-semibold tabular-nums">
                {firstShown}
              </span>{' '}
              to{' '}
              <span className="text-foreground font-semibold tabular-nums">
                {lastShown}
              </span>{' '}
              of{' '}
              <span className="text-foreground font-semibold tabular-nums">
                {total}
              </span>{' '}
              {total === 1 ? 'brief' : 'briefs'}
            </p>

            <BriefsGrid briefs={pagedBriefs} />

            {totalPages > 1 ? (
              <Pagination
                page={safePage}
                totalPages={totalPages}
                onPageChange={setPage}
                activePageClassName="bg-danger text-white"
              />
            ) : null}
          </div>
        </div>

        <BriefsLibrarySidebar
          categories={categories}
          coverage={coverage}
          total={stats.total}
          activeCategory={filters.category}
          onSelectCategory={value => updateFilters({ category: value })}
        />
      </div>
    </div>
  );
};
