'use client';

import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import type { AlertsCategoryFilterValue } from '@/data/apiAlertCategories';
import { DASHBOARD_RISK_LEGEND_ITEMS } from '@/data/dashboardRiskLegend';
import {
  alertMatchesSubscriberRiskFilter,
  type AlertsRiskFilterValue,
} from '@/data/alertRiskFilterOptions';
import { useAlertsPageQuery } from '@/hooks/useAlertsPageQuery';
import { useAlertsSearchQuery } from '@/hooks/useAlertsSearchQuery';
import { useAlertsStatsQuery } from '@/hooks/useAlertsStatsQuery';
import { alertsListQueryParsers } from '@/lib/alertsNuqsParsers';
import { buildAlertsListQueryString } from '@/lib/alertsUrlState';
import {
  ALERTS_PAGE_SIZE,
  mapAlertsStatsToRiskCounts,
  mapApiAlertToAlertItem,
} from '@/lib/api/alerts';
import type { HttpRequestError } from '@/lib/api/client';
import { formatDashboardLastUpdatedUtc } from '@/lib/formatDashboardDate';
import type { AlertApiRecord } from '@/types/alertsApi';
import { Loader2 } from 'lucide-react';
import { useQueryStates } from 'nuqs';
import { type FC, useEffect, useMemo, useState } from 'react';

import { AlertTable } from './AlertTable';
import { AlertsFiltersBar } from './AlertsFiltersBar';
import { AlertsPageHeader } from './AlertsPageHeader';
import { AlertsRiskLegendStrip } from './AlertsRiskLegendStrip';
import { AlertsSummaryLine } from './AlertsSummaryLine';
import { EarlyAccessModal } from './EarlyAccessModal';
import { Pagination } from './Pagination';

function getQueryErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    const e = error as HttpRequestError;
    if (typeof e.status === 'number') {
      return `The server returned an error (${e.status}). ${e.message}`;
    }
    return error.message;
  }
  return 'Unable to load alerts. Please try again.';
}

function filterAlertsRecordsByBrowsingFilters(
  records: AlertApiRecord[],
  risk: AlertsRiskFilterValue,
  category: string,
): AlertApiRecord[] {
  return records.filter(record => {
    if (!alertMatchesSubscriberRiskFilter(record, risk)) return false;
    if (category !== 'all' && record.category !== category) return false;
    return true;
  });
}

/** Critical / High legend only — Medium & Low are not subscriber-facing. */
const SUBSCRIBER_ALERTS_LEGEND_ITEMS = DASHBOARD_RISK_LEGEND_ITEMS.filter(
  item => item.id === 'critical' || item.id === 'high',
);

export const AlertsScreen: FC = () => {
  const [
    { risk: riskFilter, category: categoryFilter, page, q: searchQueryRaw },
    setAlertsListQuery,
  ] = useQueryStates(alertsListQueryParsers, {
    history: 'replace',
    scroll: false,
  });
  const [earlyAccessOpen, setEarlyAccessOpen] = useState(false);

  const searchTerm = searchQueryRaw.trim();
  const isSearchActive = searchTerm.length > 0;

  const listReturnQuery = buildAlertsListQueryString(
    riskFilter,
    page,
    categoryFilter,
    searchTerm || undefined,
  );

  const listQuery = useAlertsPageQuery(page, riskFilter, categoryFilter, {
    enabled: !isSearchActive,
  });

  const searchQuery = useAlertsSearchQuery(searchTerm, {
    enabled: isSearchActive,
  });

  const activeQuery = isSearchActive ? searchQuery : listQuery;

  const {
    data,
    isPending,
    isError,
    isFetching,
    error,
    dataUpdatedAt,
  } = activeQuery;

  const { data: statsData, refetch: refetchStats } =
    useAlertsStatsQuery(categoryFilter);

  const riskCounts = useMemo(
    () => (statsData ? mapAlertsStatsToRiskCounts(statsData) : undefined),
    [statsData],
  );

  const searchRecordsFiltered = useMemo(() => {
    if (!isSearchActive || !searchQuery.data?.alerts) return [];
    return filterAlertsRecordsByBrowsingFilters(
      searchQuery.data.alerts,
      riskFilter,
      categoryFilter,
    );
  }, [isSearchActive, searchQuery.data, riskFilter, categoryFilter]);

  const browseAlerts = useMemo(() => {
    const records = listQuery.data?.alerts ?? [];
    return records
      .filter(record => alertMatchesSubscriberRiskFilter(record, riskFilter))
      .map(mapApiAlertToAlertItem);
  }, [listQuery.data?.alerts, riskFilter]);

  const searchAlertsAllPages = useMemo(
    () => searchRecordsFiltered.map(mapApiAlertToAlertItem),
    [searchRecordsFiltered],
  );

  const alerts = useMemo(() => {
    if (!isSearchActive) return browseAlerts;
    const start = (page - 1) * ALERTS_PAGE_SIZE;
    return searchAlertsAllPages.slice(start, start + ALERTS_PAGE_SIZE);
  }, [isSearchActive, browseAlerts, searchAlertsAllPages, page]);

  const isInitialLoading = isPending && !data;
  const showFetchingIndicator = isFetching && !isInitialLoading;

  const hasNextPage = useMemo(() => {
    if (!isSearchActive) {
      return (
        !listQuery.isPlaceholderData &&
        (listQuery.data?.alerts.length ?? 0) === ALERTS_PAGE_SIZE
      );
    }
    const totalFiltered = searchAlertsAllPages.length;
    return page * ALERTS_PAGE_SIZE < totalFiltered;
  }, [
    isSearchActive,
    listQuery.isPlaceholderData,
    listQuery.data?.alerts.length,
    searchAlertsAllPages.length,
    page,
  ]);

  /** Prefer list `total`; else approximate from `/alerts/stats` for current risk + category. */
  const listTotalForPagination = useMemo(() => {
    if (isSearchActive) {
      const n = searchAlertsAllPages.length;
      return n > 0 ? n : 0;
    }
    const raw = !listQuery.isPlaceholderData
      ? (listQuery.data?.total ?? listQuery.data?.total_count)
      : undefined;
    const fromList =
      typeof raw === 'number' && Number.isFinite(raw) && raw >= 0
        ? raw
        : undefined;
    if (fromList !== undefined) return fromList;
    const fromStats = riskCounts?.[riskFilter];
    if (
      typeof fromStats === 'number' &&
      Number.isFinite(fromStats) &&
      fromStats >= 0
    ) {
      return fromStats;
    }
    return undefined;
  }, [
    isSearchActive,
    searchAlertsAllPages.length,
    listQuery.data?.total,
    listQuery.data?.total_count,
    listQuery.isPlaceholderData,
    riskCounts,
    riskFilter,
  ]);

  const totalPages = useMemo(() => {
    if (isSearchActive) {
      const n = searchAlertsAllPages.length;
      if (n <= 0) return undefined;
      return Math.max(1, Math.ceil(n / ALERTS_PAGE_SIZE));
    }
    if (
      typeof listTotalForPagination !== 'number' ||
      listTotalForPagination <= 0
    ) {
      return undefined;
    }
    return Math.max(1, Math.ceil(listTotalForPagination / ALERTS_PAGE_SIZE));
  }, [isSearchActive, searchAlertsAllPages.length, listTotalForPagination]);

  useEffect(() => {
    if (isSearchActive) return;
    if (listQuery.isError || listQuery.isPending || listQuery.isPlaceholderData)
      return;
    if ((listQuery.data?.alerts.length ?? 0) === 0 && page > 1) {
      void setAlertsListQuery(
        { page: 1 },
        { history: 'replace', scroll: false },
      );
    }
  }, [
    isSearchActive,
    listQuery.data?.alerts.length,
    listQuery.isError,
    listQuery.isPending,
    listQuery.isPlaceholderData,
    page,
    setAlertsListQuery,
  ]);

  useEffect(() => {
    if (!isSearchActive) return;
    if (searchQuery.isPending || searchQuery.isPlaceholderData) return;
    const totalFiltered = searchAlertsAllPages.length;
    const maxPage = Math.max(1, Math.ceil(totalFiltered / ALERTS_PAGE_SIZE));
    if (totalFiltered === 0 && page > 1) {
      void setAlertsListQuery(
        { page: 1 },
        { history: 'replace', scroll: false },
      );
    } else if (page > maxPage) {
      void setAlertsListQuery(
        { page: maxPage },
        { history: 'replace', scroll: false },
      );
    }
  }, [
    isSearchActive,
    page,
    searchAlertsAllPages.length,
    searchQuery.isPending,
    searchQuery.isPlaceholderData,
    setAlertsListQuery,
  ]);

  const lastUpdatedLabel =
    dataUpdatedAt > 0
      ? formatDashboardLastUpdatedUtc(new Date(dataUpdatedAt).toISOString())
      : null;

  const summaryFilterTotal = useMemo(() => {
    if (!isSearchActive) return riskCounts?.[riskFilter];
    return searchAlertsAllPages.length;
  }, [
    isSearchActive,
    riskCounts,
    riskFilter,
    searchAlertsAllPages.length,
  ]);

  const emptyTitle = isSearchActive ? 'No matching alerts' : 'No alerts';
  const emptyDescription = isSearchActive
    ? `Nothing matched “${searchTerm}” with the current risk and category filters. Try different keywords or filters.`
    : 'There are no alerts for this risk level or category on this page. Try another filter or go to the previous page.';

  const handleRefresh = () => {
    void refetchStats();
    if (isSearchActive) void searchQuery.refetch();
    else void listQuery.refetch();
  };

  return (
    <div className="space-y-4">
      <AlertsPageHeader
        title="Alerts"
        subtitle="Review intelligence signals and system activity."
        lastUpdatedLabel={lastUpdatedLabel}
        onRefresh={handleRefresh}
        onEarlyAccess={() => setEarlyAccessOpen(true)}
      />

      <EarlyAccessModal
        open={earlyAccessOpen}
        onClose={() => setEarlyAccessOpen(false)}
      />

      <AlertsFiltersBar
        riskFilter={riskFilter}
        categoryFilter={categoryFilter}
        riskCounts={riskCounts}
        activeSearchQuery={searchTerm || null}
        onClearSearch={() =>
          void setAlertsListQuery(
            { q: '', page: 1 },
            { history: 'replace', scroll: false },
          )
        }
        onRiskChange={value =>
          void setAlertsListQuery(
            { risk: value, page: 1 },
            { history: 'replace', scroll: false },
          )
        }
        onCategoryChange={value =>
          void setAlertsListQuery(
            {
              category: value as AlertsCategoryFilterValue,
              page: 1,
            },
            { history: 'replace', scroll: false },
          )
        }
      />

      {isError ? (
        <ErrorState
          message={getQueryErrorMessage(error)}
          onRetry={() => {
            handleRefresh();
          }}
        />
      ) : isInitialLoading ? (
        <LoadingState
          label={isSearchActive ? 'Searching alerts…' : 'Loading alerts…'}
        />
      ) : (
        <>
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
              <span>
                {isSearchActive ? 'Searching alerts…' : 'Updating alerts…'}
              </span>
            </div>
          ) : null}

          <AlertsSummaryLine
            risk={riskFilter}
            page={page}
            filterTotal={summaryFilterTotal}
            totalPages={totalPages}
            activeSearchQuery={isSearchActive ? searchTerm : null}
          />

          <AlertsRiskLegendStrip items={SUBSCRIBER_ALERTS_LEGEND_ITEMS} />

          <div
            className={
              showFetchingIndicator
                ? 'opacity-70 transition-opacity'
                : 'opacity-100'
            }
          >
            {alerts.length === 0 ? (
              <EmptyState title={emptyTitle} description={emptyDescription} />
            ) : (
              <AlertTable
                alerts={alerts}
                alertsListReturnQuery={listReturnQuery}
              />
            )}
          </div>

          {!isError &&
          !isInitialLoading &&
          ((typeof totalPages === 'number' && totalPages > 1) ||
            (typeof totalPages !== 'number' && (page > 1 || hasNextPage))) ? (
            <Pagination
              page={page}
              onPageChange={nextPage =>
                void setAlertsListQuery(
                  { page: nextPage },
                  { history: 'replace', scroll: false },
                )
              }
              totalPages={totalPages}
              hasNextPage={hasNextPage}
              activePageClassName="bg-danger text-white"
            />
          ) : null}
        </>
      )}
    </div>
  );
};
