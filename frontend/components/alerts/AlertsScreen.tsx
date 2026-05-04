'use client';

import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import type { AlertsCategoryFilterValue } from '@/data/apiAlertCategories';
import { DASHBOARD_RISK_LEGEND_ITEMS } from '@/data/dashboardRiskLegend';
import { useAlertsPageQuery } from '@/hooks/useAlertsPageQuery';
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

export const AlertsScreen: FC = () => {
  const [
    { risk: riskFilter, category: categoryFilter, page },
    setAlertsListQuery,
  ] = useQueryStates(alertsListQueryParsers, {
    history: 'replace',
    scroll: false,
  });
  const [earlyAccessOpen, setEarlyAccessOpen] = useState(false);

  const listReturnQuery = buildAlertsListQueryString(
    riskFilter,
    page,
    categoryFilter,
  );

  const {
    data,
    isPending,
    isError,
    isFetching,
    error,
    refetch,
    dataUpdatedAt,
    isPlaceholderData,
  } = useAlertsPageQuery(page, riskFilter, categoryFilter);

  const { data: statsData, refetch: refetchStats } =
    useAlertsStatsQuery(categoryFilter);

  const riskCounts = useMemo(
    () => (statsData ? mapAlertsStatsToRiskCounts(statsData) : undefined),
    [statsData],
  );

  const isInitialLoading = isPending && !data;

  const alerts = useMemo(
    () => (data?.alerts ?? []).map(mapApiAlertToAlertItem),
    [data?.alerts],
  );

  const hasNextPage =
    !isPlaceholderData && (data?.alerts.length ?? 0) === ALERTS_PAGE_SIZE;

  /** Prefer list `total`; else approximate from `/alerts/stats` for current risk + category. */
  const listTotalForPagination = useMemo(() => {
    const raw =
      !isPlaceholderData ? (data?.total ?? data?.total_count) : undefined;
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
    data?.total,
    data?.total_count,
    isPlaceholderData,
    riskCounts,
    riskFilter,
  ]);

  const totalPages = useMemo(() => {
    if (
      typeof listTotalForPagination !== 'number' ||
      listTotalForPagination <= 0
    ) {
      return undefined;
    }
    return Math.max(1, Math.ceil(listTotalForPagination / ALERTS_PAGE_SIZE));
  }, [listTotalForPagination]);

  useEffect(() => {
    if (isError || isPending || isPlaceholderData) return;
    if ((data?.alerts.length ?? 0) === 0 && page > 1) {
      void setAlertsListQuery(
        { page: 1 },
        { history: 'replace', scroll: false },
      );
    }
  }, [
    data?.alerts.length,
    isError,
    isPending,
    isPlaceholderData,
    page,
    setAlertsListQuery,
  ]);

  const lastUpdatedLabel =
    dataUpdatedAt > 0
      ? formatDashboardLastUpdatedUtc(new Date(dataUpdatedAt).toISOString())
      : null;

  return (
    <div className="space-y-4">
      <AlertsPageHeader
        title="Alerts"
        subtitle="Review intelligence signals and system activity."
        lastUpdatedLabel={lastUpdatedLabel}
        onRefresh={() => {
          void refetch();
          void refetchStats();
        }}
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
            void refetch();
            void refetchStats();
          }}
        />
      ) : isInitialLoading ? (
        <LoadingState label="Loading alerts…" />
      ) : (
        <>
          <AlertsSummaryLine
            risk={riskFilter}
            page={page}
            filterTotal={riskCounts?.[riskFilter]}
            totalPages={totalPages}
          />

          <AlertsRiskLegendStrip items={DASHBOARD_RISK_LEGEND_ITEMS} />

          <div
            className={
              isFetching ? 'opacity-70 transition-opacity' : 'opacity-100'
            }
          >
            {alerts.length === 0 ? (
              <EmptyState
                title="No alerts"
                description="There are no alerts for this risk level or category on this page. Try another filter or go to the previous page."
              />
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
