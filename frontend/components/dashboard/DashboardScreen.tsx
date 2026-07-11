'use client';

import {
  AlertsSearchForm,
  AlertsSearchFormFallback,
} from '@/components/alerts/AlertsSearchForm';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/contexts/AuthProvider';
import {
  DASHBOARD_SEARCH_ALERTS_LIMIT,
  DASHBOARD_SEARCH_GROUP_LIMIT,
  DASHBOARD_TOP_ALERTS_WEEK_LIMIT,
  useAlertsSearchQuery,
  useAlertsStatsQuery,
  useDashboardBriefsPreviewQuery,
  useDashboardTopAlertsWeekQuery,
} from '@/hooks';
import { mapAlertsStatsToRiskCounts } from '@/lib/api/alerts';
import { buildAlertsListQueryString } from '@/lib/alertsUrlState';
import { formatDashboardUpdatedRelative } from '@/lib/formatDashboardDate';
import { mapApiAlertToDashboardTopAlertWeeklyItem } from '@/lib/mapApiAlertToDashboardTopAlertWeekly';
import { AlertTriangle, ShieldAlert } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { FC } from 'react';
import { Suspense, useMemo } from 'react';

import { DashboardCriticalRiskCard } from './DashboardCriticalRiskCard';
import { DashboardIntelligenceBriefs } from './DashboardIntelligenceBriefs';
import { DashboardRecentBriefsTable } from './DashboardRecentBriefsTable';
import { DashboardTopAlertsThisWeek } from './DashboardTopAlertsThisWeek';
import { DashboardWelcomeHeader } from './DashboardWelcomeHeader';

function deriveFirstName(
  metadataFullName: string | undefined,
  email: string | null,
): string {
  if (metadataFullName && metadataFullName.trim().length > 0) {
    const first = metadataFullName.trim().split(/\s+/)[0];
    if (first) return first;
  }
  if (email) {
    const local = email.split('@')[0] ?? email;
    if (local.length > 0) {
      return local.charAt(0).toUpperCase() + local.slice(1);
    }
  }
  return 'there';
}

export const DashboardScreen: FC = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, subscriber } = useAuth();
  const searchQueryRaw = searchParams.get('q') ?? '';
  const searchTerm = searchQueryRaw.trim();
  const isSearchActive = searchTerm.length > 0;

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

  const searchQuery = useAlertsSearchQuery(searchTerm, {
    enabled: isSearchActive,
    limit: DASHBOARD_SEARCH_ALERTS_LIMIT,
    groupLimit: DASHBOARD_SEARCH_GROUP_LIMIT,
  });

  const searchRecords = searchQuery.data?.alerts;

  const {
    data: topAlertsWeekData,
    refetch: refetchTopAlertsWeek,
    isError: topAlertsWeekError,
    isPending: topAlertsWeekPending,
    dataUpdatedAt: topAlertsWeekUpdatedAt,
  } = useDashboardTopAlertsWeekQuery({ enabled: !isSearchActive });

  const {
    data: briefsPreview,
    refetch: refetchBriefsPreview,
    isError: briefsPreviewError,
    isPending: briefsPreviewPending,
    dataUpdatedAt: briefsPreviewUpdatedAt,
  } = useDashboardBriefsPreviewQuery({ enabled: !isSearchActive });

  const dashboardBriefs = briefsPreview?.items ?? [];

  const searchPartition = useMemo(() => {
    if (!isSearchActive || !searchRecords) {
      return { critical: 0, high: 0 };
    }
    let critical = 0;
    let high = 0;
    for (const record of searchRecords) {
      if (record.risk_band?.trim().toLowerCase() === 'critical') critical += 1;
      else if (record.risk_level?.trim().toLowerCase() === 'high') high += 1;
    }
    return { critical, high };
  }, [isSearchActive, searchRecords]);

  const topAlertsFromSearch = useMemo(() => {
    if (!isSearchActive || !searchRecords?.length) return [];
    return [...searchRecords]
      .sort((a, b) => b.signal_score - a.signal_score)
      .slice(0, DASHBOARD_TOP_ALERTS_WEEK_LIMIT)
      .map(item => mapApiAlertToDashboardTopAlertWeeklyItem(item));
  }, [isSearchActive, searchRecords]);

  const topAlerts = isSearchActive
    ? topAlertsFromSearch
    : (topAlertsWeekData ?? []);

  const criticalCount = isSearchActive
    ? searchPartition.critical
    : (statsData?.critical_count ?? 0);
  const highCount = isSearchActive
    ? searchPartition.high
    : (statsCounts?.high ?? 0);

  const alertsContinueHref = useMemo(() => {
    const q = isSearchActive ? searchTerm : undefined;
    const qs = (risk: string) =>
      buildAlertsListQueryString(risk, 1, 'all', q);
    const allQs = buildAlertsListQueryString('all', 1, 'all', q);
    return {
      critical: allQs ? `/alerts?${allQs}` : '/alerts',
      high: qs('high') ? `/alerts?${qs('high')}` : '/alerts?risk=high',
      all: allQs ? `/alerts?${allQs}` : '/alerts',
    };
  }, [isSearchActive, searchTerm]);

  const lastUpdatedLabel = useMemo(() => {
    if (
      isSearchActive &&
      searchQuery.dataUpdatedAt > 0 &&
      !searchQuery.isError
    ) {
      return formatDashboardUpdatedRelative(
        new Date(searchQuery.dataUpdatedAt).toISOString(),
      );
    }

    const timestamps = [
      !statsError && statsDataUpdatedAt > 0 ? statsDataUpdatedAt : 0,
      !topAlertsWeekError && topAlertsWeekUpdatedAt > 0
        ? topAlertsWeekUpdatedAt
        : 0,
      !briefsPreviewError && briefsPreviewUpdatedAt > 0
        ? briefsPreviewUpdatedAt
        : 0,
    ].filter(value => value > 0);

    if (timestamps.length > 0) {
      return formatDashboardUpdatedRelative(
        new Date(Math.max(...timestamps)).toISOString(),
      );
    }

    return 'recently';
  }, [
    isSearchActive,
    searchQuery.dataUpdatedAt,
    searchQuery.isError,
    statsDataUpdatedAt,
    statsError,
    topAlertsWeekError,
    topAlertsWeekUpdatedAt,
    briefsPreviewError,
    briefsPreviewUpdatedAt,
  ]);

  const metadataName = user?.user_metadata?.full_name;
  const fullName = typeof metadataName === 'string' ? metadataName : undefined;
  const email = subscriber?.email ?? user?.email ?? null;
  const firstName = deriveFirstName(fullName, email);

  const searchResultsLoading =
    isSearchActive && searchQuery.isPending && searchQuery.data === undefined;
  const topAlertsPendingEffective = isSearchActive
    ? searchResultsLoading
    : topAlertsWeekPending;
  const topAlertsErrorEffective = isSearchActive
    ? searchQuery.isError
    : topAlertsWeekError;
  const topAlertsStillLoading =
    topAlertsPendingEffective &&
    !(isSearchActive ? searchQuery.data : topAlertsWeekData);

  const briefsStillLoading =
    !isSearchActive &&
    briefsPreviewPending &&
    briefsPreview === undefined;

  function handleRefresh() {
    if (isSearchActive) {
      void searchQuery.refetch();
    } else {
      void refetchStats();
      void refetchTopAlertsWeek();
      void refetchBriefsPreview();
    }
    router.refresh();
  }

  const briefsBodyContent = isSearchActive ? (
    <p className="text-muted border-border mt-5 rounded-lg border border-dashed px-4 py-8 text-center text-sm">
      Brief previews are hidden while search is active. Open the briefs library
      to browse intelligence reports.
    </p>
  ) : briefsStillLoading ? (
    <LoadingState label="Loading intelligence briefs…" className="py-10" />
  ) : briefsPreviewError ? (
    <ErrorState
      title="Unable to load intelligence briefs"
      message="We could not fetch brief previews right now. Please try again."
      onRetry={() => void refetchBriefsPreview()}
      className="py-10"
    />
  ) : undefined;

  return (
    <div className="space-y-6 lg:space-y-8">
      <DashboardWelcomeHeader
        firstName={firstName}
        lastUpdatedLabel={lastUpdatedLabel}
        onRefresh={handleRefresh}
      />

      <Suspense
        fallback={
          <AlertsSearchFormFallback
            className="w-full"
            placeholder="Search briefs, alerts, or topics..."
            inputClassName="h-12 rounded-lg"
          />
        }
      >
        <AlertsSearchForm
          className="w-full"
          placeholder="Search briefs, alerts, or topics..."
          inputClassName="h-12 rounded-lg"
        />
      </Suspense>

      <div className="grid gap-4 lg:grid-cols-2">
        <DashboardCriticalRiskCard
          label="Critical Risk Alerts"
          rangeLabel="81-100"
          value={criticalCount}
          description="Immediate attention required."
          tone="critical"
          icon={<ShieldAlert className="size-6 sm:size-7" aria-hidden />}
          href={alertsContinueHref.critical}
        />
        <DashboardCriticalRiskCard
          label="High Risk Alerts"
          rangeLabel="71-80"
          value={highCount}
          description="Elevated risk requiring close monitoring."
          tone="high"
          icon={<AlertTriangle className="size-6 sm:size-7" aria-hidden />}
          href={alertsContinueHref.high}
        />
      </div>

      <DashboardIntelligenceBriefs
        briefs={dashboardBriefs}
        viewAllHref="/briefs"
        bodyContent={briefsBodyContent}
      />

      <DashboardRecentBriefsTable
        briefs={dashboardBriefs}
        viewAllHref="/briefs"
        bodyContent={briefsBodyContent}
      />

      <DashboardTopAlertsThisWeek
        alerts={topAlerts}
        viewAllHref={alertsContinueHref.all}
        viewAllLabel="View all alerts"
        bodyContent={
          topAlertsStillLoading ? (
            <LoadingState label="Loading top alerts…" className="py-12" />
          ) : topAlertsErrorEffective ? (
            <ErrorState
              title="Unable to load top alerts"
              message="We could not fetch the top alerts right now. Please try again."
              onRetry={() => {
                if (isSearchActive) void searchQuery.refetch();
                else void refetchTopAlertsWeek();
              }}
              className="py-10"
            />
          ) : topAlerts.length === 0 ? (
            <EmptyState
              title={
                isSearchActive ? 'No matching alerts' : 'No top alerts yet'
              }
              description={
                isSearchActive
                  ? 'No alerts match your search right now.'
                  : 'Top alerts will appear here once high-priority signals are available.'
              }
              className="py-10"
            />
          ) : undefined
        }
      />
    </div>
  );
};
