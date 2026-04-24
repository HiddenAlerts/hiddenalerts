'use client';

import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { API_ALERT_CATEGORY_OPTIONS } from '@/data/apiAlertCategories';
import { useAlertsPageQuery } from '@/hooks/useAlertsPageQuery';
import { ALERTS_PAGE_SIZE } from '@/lib/api/alerts';
import { mapApiAlertToAlertItem } from '@/lib/api/alerts';
import type { HttpRequestError } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import { useCallback, useMemo, useState, type FC } from 'react';

import { AlertTable } from './AlertTable';
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
  const [category, setCategory] = useState('all');
  const [page, setPage] = useState(1);

  const {
    data,
    isPending,
    isError,
    isFetching,
    error,
    refetch,
  } = useAlertsPageQuery(page, category);

  const isInitialLoading = isPending && !data;

  const alerts = useMemo(
    () => (data?.alerts ?? []).map(mapApiAlertToAlertItem),
    [data?.alerts],
  );

  const hasNextPage = (data?.alerts.length ?? 0) === ALERTS_PAGE_SIZE;

  const setCategoryAndResetPage = useCallback((value: string) => {
    setCategory(value);
    setPage(1);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight">
            Alerts
          </h1>
          <p className="text-muted mt-1 text-sm">
            Review intelligence signals and system activity.
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-muted text-xs font-medium tracking-wide uppercase">
          Category
        </p>
        <div className="flex flex-wrap gap-2">
          {API_ALERT_CATEGORY_OPTIONS.map(opt => {
            const selected = category === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => setCategoryAndResetPage(opt.value)}
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                  selected
                    ? 'bg-primary-500 text-white'
                    : 'bg-surface text-body hover:bg-surface-muted border border-transparent',
                )}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {isError ? (
        <ErrorState
          message={getQueryErrorMessage(error)}
          onRetry={() => void refetch()}
        />
      ) : isInitialLoading ? (
        <LoadingState label="Loading alerts…" />
      ) : (
        <>
          {alerts.length === 0 ? (
            <EmptyState
              title="No alerts"
              description="There are no alerts for this filter on this page. Try another category or go to the previous page."
            />
          ) : (
            <div
              className={cn(
                'transition-opacity',
                isFetching ? 'opacity-70' : 'opacity-100',
              )}
            >
              <AlertTable alerts={alerts} />
            </div>
          )}
          {!isError && !isInitialLoading && (page > 1 || hasNextPage) ? (
            <Pagination
              page={page}
              onPageChange={setPage}
              hasNextPage={hasNextPage}
            />
          ) : null}
        </>
      )}
    </div>
  );
};
