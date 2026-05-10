'use client';

import { EarlyAccessModal } from '@/components/alerts/EarlyAccessModal';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import {
  DASHBOARD_DUMMY_LAST_UPDATED_ISO,
  DASHBOARD_UNLOCK_CTA,
} from '@/data/dashboardConstants';
import {
  DASHBOARD_RISK_LEGEND_INFO,
  DASHBOARD_RISK_LEGEND_ITEMS,
} from '@/data/dashboardRiskLegend';
import { MOCK_ALERTS } from '@/data/mockAlerts';
import { useAlertsSearchQuery } from '@/hooks/useAlertsSearchQuery';
import { useAlertsStatsQuery } from '@/hooks/useAlertsStatsQuery';
import {
  DASHBOARD_RISK_PREVIEW_LIMIT,
  useDashboardRiskPreviewsQuery,
} from '@/hooks/useDashboardRiskPreviewsQuery';
import { useDashboardTopAlertsQuery } from '@/hooks/useDashboardTopAlertsQuery';
import { partitionAlertsByRisk } from '@/lib/alertRisk';
import { sortAlertsByDisplayedAtDesc } from '@/lib/alertDisplay';
import {
  mapAlertsStatsToRiskCounts,
  mapApiAlertToAlertItem,
} from '@/lib/api/alerts';
import { buildAlertsListQueryString } from '@/lib/alertsUrlState';
import { formatDashboardLastUpdatedUtc } from '@/lib/formatDashboardDate';
import { mapApiAlertToDashboardTopAlertItem } from '@/lib/mapApiAlertToDashboardTopAlert';
import { AlertTriangle, Bell, ShieldAlert, ShieldCheck } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { FC } from 'react';
import { useMemo, useState } from 'react';

import { DashboardAlertGroup } from './DashboardAlertGroup';
import { DashboardAlertListItem } from './DashboardAlertListItem';
import { DashboardPageHeader } from './DashboardPageHeader';
import { DashboardRiskScoreLegend } from './DashboardRiskScoreLegend';
import { DashboardRiskSummaryCard } from './DashboardRiskSummaryCard';
import { DashboardTopAlertsSection } from './DashboardTopAlertsSection';
import { DashboardUnlockCta } from './DashboardUnlockCta';

function pct(part: number, total: number) {
  if (total <= 0) return 0;
  return Math.round((part / total) * 100);
}

export const DashboardScreen: FC = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchQueryRaw = searchParams.get('q') ?? '';
  const searchTerm = searchQueryRaw.trim();
  const isSearchActive = searchTerm.length > 0;

  const [earlyAccessOpen, setEarlyAccessOpen] = useState(false);
  const [lastUpdatedIso, setLastUpdatedIso] = useState(
    DASHBOARD_DUMMY_LAST_UPDATED_ISO,
  );

  const {
    data: statsData,
    dataUpdatedAt: statsDataUpdatedAt,
    refetch: refetchStats,
    isError: statsError,
  } = useAlertsStatsQuery('all', { enabled: !isSearchActive });

  const statsCounts = useMemo(
    () =>
      !isSearchActive && statsData && !statsError
        ? mapAlertsStatsToRiskCounts(statsData)
        : null,
    [isSearchActive, statsData, statsError],
  );

  const {
    highQuery,
    mediumQuery,
    lowQuery,
    highAlerts,
    mediumAlerts,
    lowAlerts,
    refetchAll: refetchRiskPreviews,
  } = useDashboardRiskPreviewsQuery({ enabled: !isSearchActive });
  const {
    data: topAlertsFromApi,
    refetch: refetchTopAlerts,
    isError: topAlertsError,
    isPending: topAlertsPending,
  } = useDashboardTopAlertsQuery({ enabled: !isSearchActive });

  const searchQuery = useAlertsSearchQuery(searchTerm, {
    enabled: isSearchActive,
  });

  const searchRecords = searchQuery.data?.alerts;

  const searchItems = useMemo(() => {
    if (!isSearchActive || !searchRecords) return [];
    return searchRecords.map(mapApiAlertToAlertItem);
  }, [isSearchActive, searchRecords]);

  const searchPartition = useMemo(
    () => partitionAlertsByRisk(searchItems),
    [searchItems],
  );

  const highAlertsFromSearch = useMemo(
    () =>
      [...searchPartition.high]
        .sort(sortAlertsByDisplayedAtDesc)
        .slice(0, DASHBOARD_RISK_PREVIEW_LIMIT),
    [searchPartition.high],
  );
  const mediumAlertsFromSearch = useMemo(
    () =>
      [...searchPartition.medium]
        .sort(sortAlertsByDisplayedAtDesc)
        .slice(0, DASHBOARD_RISK_PREVIEW_LIMIT),
    [searchPartition.medium],
  );
  const lowAlertsFromSearch = useMemo(
    () =>
      [...searchPartition.low]
        .sort(sortAlertsByDisplayedAtDesc)
        .slice(0, DASHBOARD_RISK_PREVIEW_LIMIT),
    [searchPartition.low],
  );

  const topAlertsFromSearch = useMemo(() => {
    if (!isSearchActive || !searchRecords?.length) return [];
    return [...searchRecords]
      .sort((a, b) => b.signal_score - a.signal_score)
      .slice(0, 3)
      .map((item, index) => mapApiAlertToDashboardTopAlertItem(item, index));
  }, [isSearchActive, searchRecords]);

  const { high, medium, low } = useMemo(
    () => partitionAlertsByRisk(MOCK_ALERTS),
    [],
  );
  const mockTotal = MOCK_ALERTS.length;

  const totalAlerts = isSearchActive
    ? searchItems.length
    : typeof statsCounts?.all === 'number'
      ? statsCounts.all
      : mockTotal;
  const highTotal = isSearchActive
    ? searchPartition.high.length
    : typeof statsCounts?.high === 'number'
      ? statsCounts.high
      : high.length;
  const mediumTotal = isSearchActive
    ? searchPartition.medium.length
    : typeof statsCounts?.medium === 'number'
      ? statsCounts.medium
      : medium.length;
  const lowTotal = isSearchActive
    ? searchPartition.low.length
    : typeof statsCounts?.low === 'number'
      ? statsCounts.low
      : low.length;

  const alertsContinueHref = useMemo(() => {
    const q = isSearchActive ? searchTerm : undefined;
    const qs = (risk: string) =>
      buildAlertsListQueryString(risk, 1, 'all', q);
    const allQs = buildAlertsListQueryString('all', 1, 'all', q);
    return {
      high: qs('high') ? `/alerts?${qs('high')}` : '/alerts',
      medium: qs('medium') ? `/alerts?${qs('medium')}` : '/alerts',
      low: qs('low') ? `/alerts?${qs('low')}` : '/alerts',
      all: allQs ? `/alerts?${allQs}` : '/alerts',
    };
  }, [isSearchActive, searchTerm]);

  const lastUpdatedLabel = useMemo(() => {
    if (
      isSearchActive &&
      searchQuery.dataUpdatedAt > 0 &&
      !searchQuery.isError
    ) {
      return formatDashboardLastUpdatedUtc(
        new Date(searchQuery.dataUpdatedAt).toISOString(),
      );
    }
    if (statsDataUpdatedAt > 0 && statsData && !statsError) {
      return formatDashboardLastUpdatedUtc(
        new Date(statsDataUpdatedAt).toISOString(),
      );
    }
    return formatDashboardLastUpdatedUtc(lastUpdatedIso);
  }, [
    isSearchActive,
    searchQuery.dataUpdatedAt,
    searchQuery.isError,
    statsDataUpdatedAt,
    statsData,
    statsError,
    lastUpdatedIso,
  ]);

  const topAlerts = isSearchActive
    ? topAlertsFromSearch
    : (topAlertsFromApi ?? []);

  const displayedHighAlerts = isSearchActive ? highAlertsFromSearch : highAlerts;
  const displayedMediumAlerts = isSearchActive
    ? mediumAlertsFromSearch
    : mediumAlerts;
  const displayedLowAlerts = isSearchActive ? lowAlertsFromSearch : lowAlerts;

  const searchResultsLoading =
    isSearchActive && searchQuery.isPending && searchQuery.data === undefined;
  const topAlertsPendingEffective = isSearchActive
    ? searchResultsLoading
    : topAlertsPending;
  const topAlertsErrorEffective = isSearchActive
    ? searchQuery.isError
    : topAlertsError;

  const topAlertsStillLoading =
    topAlertsPendingEffective &&
    !(isSearchActive ? searchQuery.data : topAlertsFromApi);

  return (
    <div className="space-y-6 lg:space-y-8">
      <DashboardPageHeader
        title="Fraud Intelligence Dashboard"
        subtitle="Real-time monitoring of fraud, sanctions, and exposure signals."
        statusLine={
          <>
            <span className="text-danger font-semibold tabular-nums">
              {totalAlerts}
            </span>
            <span> relevant alerts detected</span>
          </>
        }
        lastUpdatedLabel={lastUpdatedLabel}
        onViewAlerts={() => router.push(alertsContinueHref.all)}
        onRefresh={() => {
          setLastUpdatedIso(new Date().toISOString());
          if (isSearchActive) {
            void searchQuery.refetch();
          } else {
            void refetchStats();
            void refetchRiskPreviews();
            void refetchTopAlerts();
          }
          router.refresh();
        }}
      />

      <DashboardTopAlertsSection
        title="Top Alerts You Should Know"
        subtitle="The highest priority alerts based on risk score and recency"
        viewAllHref={alertsContinueHref.high}
        viewAllLabel="View all high risk alerts"
        riskTone="high"
        alerts={topAlerts}
        bodyContent={
          topAlertsStillLoading ? (
            <LoadingState label="Loading top alerts…" className="py-12" />
          ) : topAlertsErrorEffective ? (
            <ErrorState
              title="Unable to load top alerts"
              message="We could not fetch the top alerts right now. Please try again."
              onRetry={() => {
                if (isSearchActive) void searchQuery.refetch();
                else void refetchTopAlerts();
              }}
              className="py-10"
            />
          ) : topAlerts.length === 0 ? (
            <EmptyState
              title="No top alerts yet"
              description="Top alerts will appear here once high-priority signals are available."
              className="py-10"
            />
          ) : undefined
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardRiskSummaryCard
          label="High risk"
          value={highTotal}
          percentOfTotal={pct(highTotal, totalAlerts)}
          tone="danger"
          href={alertsContinueHref.high}
          icon={<ShieldAlert className="size-5 sm:size-[32px]" aria-hidden />}
        />
        <DashboardRiskSummaryCard
          label="Medium risk"
          value={mediumTotal}
          percentOfTotal={pct(mediumTotal, totalAlerts)}
          tone="warning"
          href={alertsContinueHref.medium}
          icon={<AlertTriangle className="size-5 sm:size-[32px]" aria-hidden />}
        />
        <DashboardRiskSummaryCard
          label="Low risk"
          value={lowTotal}
          percentOfTotal={pct(lowTotal, totalAlerts)}
          tone="success"
          href={alertsContinueHref.low}
          icon={<ShieldCheck className="size-5 sm:size-[32px]" aria-hidden />}
        />
        <DashboardRiskSummaryCard
          label="All alerts"
          value={totalAlerts}
          percentOfTotal={totalAlerts === 0 ? 0 : 100}
          tone="info"
          href={alertsContinueHref.all}
          icon={<Bell className="size-5 sm:size-[32px]" aria-hidden />}
        />
      </div>

      <DashboardRiskScoreLegend
        items={DASHBOARD_RISK_LEGEND_ITEMS}
        infoTitle={DASHBOARD_RISK_LEGEND_INFO.title}
        infoDescription={DASHBOARD_RISK_LEGEND_INFO.description}
      />

      <div className="space-y-8">
        <DashboardAlertGroup
          title="High Risk Alerts"
          count={highTotal}
          viewAllHref={alertsContinueHref.high}
          riskTone="high"
          emptyMessage="No high-risk alerts."
        >
          {isSearchActive ? (
            searchResultsLoading ? (
              <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
                Loading alerts…
              </p>
            ) : (
              displayedHighAlerts.map(alert => (
                <DashboardAlertListItem key={alert.id} alert={alert} />
              ))
            )
          ) : highQuery.isPending && !highQuery.data ? (
            <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
              Loading alerts…
            </p>
          ) : (
            displayedHighAlerts.map(alert => (
              <DashboardAlertListItem key={alert.id} alert={alert} />
            ))
          )}
        </DashboardAlertGroup>

        <DashboardAlertGroup
          title="Medium Risk Alerts"
          count={mediumTotal}
          viewAllHref={alertsContinueHref.medium}
          riskTone="medium"
          emptyMessage="No medium-risk alerts."
        >
          {isSearchActive ? (
            searchResultsLoading ? (
              <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
                Loading alerts…
              </p>
            ) : (
              displayedMediumAlerts.map(alert => (
                <DashboardAlertListItem key={alert.id} alert={alert} />
              ))
            )
          ) : mediumQuery.isPending && !mediumQuery.data ? (
            <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
              Loading alerts…
            </p>
          ) : (
            displayedMediumAlerts.map(alert => (
              <DashboardAlertListItem key={alert.id} alert={alert} />
            ))
          )}
        </DashboardAlertGroup>

        <DashboardAlertGroup
          title="Low Risk Alerts"
          count={lowTotal}
          viewAllHref={alertsContinueHref.low}
          riskTone="low"
          emptyMessage="No low-risk alerts."
          collapsible
          defaultCollapsed
          collapsedSummary="Low risk alerts are collapsed by default"
        >
          {isSearchActive ? (
            searchResultsLoading ? (
              <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
                Loading alerts…
              </p>
            ) : (
              displayedLowAlerts.map(alert => (
                <DashboardAlertListItem key={alert.id} alert={alert} />
              ))
            )
          ) : lowQuery.isPending && !lowQuery.data ? (
            <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
              Loading alerts…
            </p>
          ) : (
            displayedLowAlerts.map(alert => (
              <DashboardAlertListItem key={alert.id} alert={alert} />
            ))
          )}
        </DashboardAlertGroup>
      </div>

      <DashboardUnlockCta
        title={DASHBOARD_UNLOCK_CTA.title}
        description={DASHBOARD_UNLOCK_CTA.description}
        primaryLabel={DASHBOARD_UNLOCK_CTA.primaryLabel}
        secondaryLabel={DASHBOARD_UNLOCK_CTA.secondaryLabel}
        secondaryHref="/"
        onPrimaryClick={() => setEarlyAccessOpen(true)}
      />

      <EarlyAccessModal
        open={earlyAccessOpen}
        onClose={() => setEarlyAccessOpen(false)}
      />
    </div>
  );
};
