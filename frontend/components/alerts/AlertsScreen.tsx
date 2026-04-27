'use client';

import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { API_ALERT_CATEGORY_OPTIONS } from '@/data/apiAlertCategories';
import { useAlertsPageQuery } from '@/hooks/useAlertsPageQuery';
import { scoreVisualTone } from '@/lib/alertDisplay';
import { presentFeaturedSignalCopy } from '@/lib/featuredSignalPresentation';
import { ALERTS_PAGE_SIZE } from '@/lib/api/alerts';
import { mapApiAlertToAlertItem } from '@/lib/api/alerts';
import type { HttpRequestError } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import type { AlertItem } from '@/types/alert';
import { type FC, useCallback, useMemo, useState } from 'react';

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

function selectFeaturedSignal(alerts: AlertItem[]): AlertItem | null {
  if (alerts.length === 0) return null;
  const ranked = [...alerts].sort((a, b) => {
    const scoreA = typeof a.signalScore === 'number' ? a.signalScore : -1;
    const scoreB = typeof b.signalScore === 'number' ? b.signalScore : -1;
    return scoreB - scoreA;
  });
  return ranked[0] ?? null;
}

const scoreTextColor: Record<ReturnType<typeof scoreVisualTone>, string> = {
  danger: 'text-danger',
  warning: 'text-warning',
  success: 'text-success',
  muted: 'text-body',
};

export const AlertsScreen: FC = () => {
  const [category, setCategory] = useState('all');
  const [page, setPage] = useState(1);

  const { data, isPending, isError, isFetching, error, refetch } =
    useAlertsPageQuery(page, category);

  const isInitialLoading = isPending && !data;

  const alerts = useMemo(
    () => (data?.alerts ?? []).map(mapApiAlertToAlertItem),
    [data?.alerts],
  );

  const hasNextPage = (data?.alerts.length ?? 0) === ALERTS_PAGE_SIZE;

  const featuredSignal = useMemo(() => selectFeaturedSignal(alerts), [alerts]);

  const featuredDisplay = useMemo(
    () =>
      featuredSignal ? presentFeaturedSignalCopy(featuredSignal) : null,
    [featuredSignal],
  );

  const gridAlerts = useMemo(
    () => alerts.filter(alert => alert.id !== featuredSignal?.id),
    [alerts, featuredSignal?.id],
  );

  const commandStats = useMemo(() => {
    const highRiskCount = alerts.filter(
      alert => alert.riskLevelLabel.toUpperCase() === 'HIGH',
    ).length;
    const scores = alerts
      .map(alert => alert.signalScore)
      .filter((score): score is number => typeof score === 'number');
    const averageScore =
      scores.length > 0
        ? Math.round(
            scores.reduce((sum, score) => sum + score, 0) / scores.length,
          )
        : null;
    const activeSources = Array.from(
      new Set(
        alerts
          .map(alert => (alert.sourceDisplayLabel ?? alert.sourceLabel).trim())
          .filter(Boolean),
      ),
    );
    return { highRiskCount, averageScore, activeSources };
  }, [alerts]);

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
        <p className="text-muted text-xs font-semibold tracking-[0.14em] uppercase">
          Command Bar
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <article className="border-border bg-surface/45 rounded-lg border px-4 py-3.5">
            <p className="text-muted text-[0.67rem] font-semibold tracking-[0.15em] uppercase">
              High-risk signals
            </p>
            <p className="text-danger mt-2 text-3xl leading-none font-bold tabular-nums">
              {commandStats.highRiskCount}
            </p>
            <p className="text-muted/75 mt-1 text-xs">Active now</p>
          </article>
          <article className="border-border bg-surface/45 rounded-lg border px-4 py-3.5">
            <p className="text-muted text-[0.67rem] font-semibold tracking-[0.15em] uppercase">
              New signals (24h)
            </p>
            <p className="text-info mt-2 text-3xl leading-none font-bold tabular-nums">
              {alerts.length}
            </p>
            <p className="text-muted/75 mt-1 text-xs">Latest batch</p>
          </article>
          <article className="border-border bg-surface/45 rounded-lg border px-4 py-3.5">
            <p className="text-muted text-[0.67rem] font-semibold tracking-[0.15em] uppercase">
              Avg signal score
            </p>
            <p className="text-success mt-2 text-3xl leading-none font-bold tabular-nums">
              {commandStats.averageScore ?? '—'}
            </p>
            <p className="text-muted/75 mt-1 text-xs">Current feed</p>
          </article>
          <article className="border-border bg-surface/45 rounded-lg border px-4 py-3.5">
            <p className="text-muted text-[0.67rem] font-semibold tracking-[0.15em] uppercase">
              Active sources
            </p>
            <p className="text-foreground mt-2 line-clamp-1 text-lg leading-tight font-semibold">
              {commandStats.activeSources.slice(0, 3).join(' / ') || '—'}
            </p>
            <p className="text-muted/75 mt-1 text-xs">
              {commandStats.activeSources.length} sources online
            </p>
          </article>
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
            <>
              {featuredSignal ? (
                <article className="border-danger/45 from-danger/10 via-primary-900/20 to-surface/80 rounded-xl border bg-gradient-to-r px-5 py-4.5">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="mb-2 flex items-center gap-2.5">
                        <span className="border-danger/70 bg-danger/24 text-danger inline-flex items-center rounded-md border px-3 py-1 text-xs font-extrabold tracking-[0.09em] uppercase">
                          {featuredSignal.riskLevelLabel}
                        </span>
                        <span className="text-muted/85 text-xs font-medium">
                          Featured Signal
                        </span>
                      </div>
                      <h2 className="font-heading text-foreground line-clamp-2 text-2xl leading-tight font-semibold tracking-tight">
                        {featuredDisplay?.title ?? featuredSignal.title}
                      </h2>
                      <p className="text-body/95 mt-2 line-clamp-3 max-w-3xl text-sm leading-relaxed">
                        {featuredDisplay?.description ?? featuredSignal.description}
                      </p>
                      {featuredSignal.sourceUrl ? (
                        <a
                          href={featuredSignal.sourceUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-danger mt-3 inline-flex text-sm font-semibold"
                        >
                          View Full Signal →
                        </a>
                      ) : null}
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-muted/80 text-xs font-semibold tracking-[0.12em] uppercase">
                        Score
                      </p>
                      <p
                        className={cn(
                          'mt-1 text-6xl leading-none font-bold tabular-nums',
                          scoreTextColor[
                            scoreVisualTone(
                              featuredSignal.signalScore,
                              featuredSignal.riskLevelLabel,
                            )
                          ],
                        )}
                      >
                        {featuredSignal.signalScore ?? '—'}
                      </p>
                    </div>
                  </div>
                </article>
              ) : null}

              <section className="space-y-3">
                <div className="border-border bg-surface/30 flex flex-col gap-3 rounded-lg border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {API_ALERT_CATEGORY_OPTIONS.map(opt => {
                      const selected = category === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => setCategoryAndResetPage(opt.value)}
                          className={cn(
                            'cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
                            selected
                              ? 'border-primary-500 bg-primary-500 text-white'
                              : 'border-border bg-surface text-body hover:bg-surface-muted',
                          )}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div
                  className={cn(
                    'transition-opacity',
                    isFetching ? 'opacity-70' : 'opacity-100',
                  )}
                >
                  {gridAlerts.length === 0 ? (
                    <EmptyState
                      title="No additional signals"
                      description="The featured signal is currently the only item on this page."
                    />
                  ) : (
                    <AlertTable alerts={gridAlerts} />
                  )}
                </div>
              </section>
            </>
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
