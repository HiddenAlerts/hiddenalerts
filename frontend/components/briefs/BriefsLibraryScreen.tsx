'use client';

import { Pagination } from '@/components/alerts/Pagination';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import {
  useDebouncedValue,
  useSubscriberBriefsOverviewQuery,
  useSubscriberBriefsPageQuery,
  useSubscriberFeaturedBriefQuery,
} from '@/hooks';
import { getApiErrorMessage } from '@/lib/api/queryError';
import { SUBSCRIBER_BRIEFS_PAGE_SIZE } from '@/lib/api/subscriberBriefs';
import type { BriefFilters, BriefSortValue, SubscriberBrief } from '@/types/briefs';
import { Loader2 } from 'lucide-react';
import { type FC, useMemo, useState } from 'react';

import { BriefsGrid } from './BriefsGrid';
import { BriefsLibraryHeader } from './BriefsLibraryHeader';
import { BriefsLibrarySidebar } from './BriefsLibrarySidebar';
import { BriefsStatsRow } from './BriefsStatsRow';
import { FeaturedBriefCard } from './FeaturedBriefCard';
import { RecentAdditions } from './RecentAdditions';

const DEFAULT_FILTERS: BriefFilters = {
  search: '',
  category: 'all',
  risk: 'all',
  sort: 'newest',
};

const SEARCH_DEBOUNCE_MS = 400;

/**
 * The backend always returns briefs newest-first with no sort parameter, so
 * "sort" only reorders the briefs already on the current page — not the
 * whole library. Everything else (search/category/risk, pagination) is
 * server-side.
 */
function sortPageItems(
  items: SubscriberBrief[],
  sort: BriefSortValue,
): SubscriberBrief[] {
  const sorted = [...items];
  switch (sort) {
    case 'oldest':
      return sorted.sort((a, b) => a.date.localeCompare(b.date));
    case 'risk-high':
      return sorted.sort((a, b) => b.riskScore - a.riskScore);
    case 'risk-low':
      return sorted.sort((a, b) => a.riskScore - b.riskScore);
    case 'newest':
    default:
      return sorted;
  }
}

export const BriefsLibraryScreen: FC = () => {
  const [filters, setFilters] = useState<BriefFilters>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebouncedValue(filters.search, SEARCH_DEBOUNCE_MS);

  const pageQuery = useSubscriberBriefsPageQuery({
    page,
    search: debouncedSearch,
    category: filters.category,
    risk: filters.risk,
  });
  const overviewQuery = useSubscriberBriefsOverviewQuery();
  const featuredQuery = useSubscriberFeaturedBriefQuery();

  const hasActiveFilters =
    filters.search.trim() !== '' ||
    filters.category !== 'all' ||
    filters.risk !== 'all' ||
    filters.sort !== 'newest';

  function updateFilters(patch: Partial<BriefFilters>) {
    setFilters(prev => ({ ...prev, ...patch }));
    setPage(1);
  }

  const categoryOptions = useMemo(
    () => [
      { value: 'all', label: 'All Categories' },
      ...(overviewQuery.data?.categories ?? []).map(category => ({
        value: category.label,
        label: category.label,
      })),
    ],
    [overviewQuery.data?.categories],
  );

  const items = useMemo(
    () => sortPageItems(pageQuery.data?.items ?? [], filters.sort),
    [pageQuery.data?.items, filters.sort],
  );

  const isInitialLoading =
    (pageQuery.isPending && !pageQuery.data) || overviewQuery.isPending;
  const showFetchingIndicator = pageQuery.isFetching && !isInitialLoading;

  if (isInitialLoading) {
    return <LoadingState label="Loading intelligence briefs…" />;
  }

  if (pageQuery.isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(
          pageQuery.error,
          'Unable to load intelligence briefs. Please try again.',
        )}
        onRetry={() => void pageQuery.refetch()}
      />
    );
  }

  const total = pageQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / SUBSCRIBER_BRIEFS_PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const firstShown = total === 0 ? 0 : (safePage - 1) * SUBSCRIBER_BRIEFS_PAGE_SIZE + 1;
  const lastShown = Math.min(safePage * SUBSCRIBER_BRIEFS_PAGE_SIZE, total);
  const showHighlights = !hasActiveFilters && safePage === 1;

  return (
    <div className="space-y-6">
      <BriefsLibraryHeader
        filters={filters}
        categoryOptions={categoryOptions}
        onSearchChange={value => updateFilters({ search: value })}
        onCategoryChange={value => updateFilters({ category: value })}
        onRiskChange={value => updateFilters({ risk: value })}
        onSortChange={value => updateFilters({ sort: value })}
        onReset={() => {
          setFilters(DEFAULT_FILTERS);
          setPage(1);
        }}
        hasActiveFilters={hasActiveFilters}
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem] xl:gap-6">
        <div className="min-w-0 space-y-5">
          <BriefsStatsRow
            stats={overviewQuery.data?.stats ?? { total: 0, critical: 0, high: 0 }}
            featured={featuredQuery.data ?? undefined}
          />

          {showHighlights && featuredQuery.data ? (
            <FeaturedBriefCard brief={featuredQuery.data} />
          ) : null}

          {showHighlights ? (
            <RecentAdditions
              briefs={overviewQuery.data?.recent ?? []}
              viewAllHref="/briefs#brief-library-results"
            />
          ) : null}

          <div
            id="brief-library-results"
            className="scroll-mt-24 space-y-3"
          >
            {showFetchingIndicator ? (
              <div
                role="status"
                aria-live="polite"
                aria-busy="true"
                className="border-border bg-surface/40 text-muted flex items-center gap-2 rounded-sm border px-3 py-2 text-sm font-medium"
              >
                <Loader2
                  className="text-primary-400 size-4 shrink-0 animate-spin"
                  strokeWidth={2}
                  aria-hidden
                />
                <span>Updating briefs…</span>
              </div>
            ) : null}

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

            <BriefsGrid briefs={items} />

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
          categories={overviewQuery.data?.categories ?? []}
          total={overviewQuery.data?.stats.total ?? 0}
          activeCategory={filters.category}
          onSelectCategory={value => updateFilters({ category: value })}
        />
      </div>
    </div>
  );
};
