'use client';

import {
  AlertsSearchForm,
  AlertsSearchFormFallback,
} from '@/components/alerts/AlertsSearchForm';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/contexts/AuthProvider';
import { DASHBOARD_DUMMY_LAST_UPDATED_ISO } from '@/data/dashboardConstants';
import { DASHBOARD_MOCK_BRIEFS } from '@/data/dashboardBriefs';
import { DASHBOARD_RECENT_BRIEFS } from '@/data/dashboardRecentBriefs';
import { MOCK_ALERTS } from '@/data/mockAlerts';
import { useAlertsSearchQuery } from '@/hooks/useAlertsSearchQuery';
import { useAlertsStatsQuery } from '@/hooks/useAlertsStatsQuery';
import { useDashboardTopAlertsWeekQuery } from '@/hooks/useDashboardTopAlertsWeekQuery';
import { partitionAlertsByRisk } from '@/lib/alertRisk';
import {
  mapAlertsStatsToRiskCounts,
} from '@/lib/api/alerts';
import { buildAlertsListQueryString } from '@/lib/alertsUrlState';
import { formatDashboardUpdatedRelative } from '@/lib/formatDashboardDate';
import { mapApiAlertToDashboardTopAlertWeeklyItem } from '@/lib/mapApiAlertToDashboardTopAlertWeekly';
import { AlertTriangle, ShieldAlert } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { FC } from 'react';
import { Suspense, useMemo, useState } from 'react';

import { DashboardCriticalRiskCard } from './DashboardCriticalRiskCard';
import { DashboardIntelligenceBriefs } from './DashboardIntelligenceBriefs';
import { DashboardRecentBriefsTable } from './DashboardRecentBriefsTable';
import { DashboardTopAlertsThisWeek } from './DashboardTopAlertsThisWeek';
import { DashboardWelcomeHeader } from './DashboardWelcomeHeader';

const NEW_CRITICAL_SINCE_LAST_LOGIN = 5;
const NEW_HIGH_SINCE_LAST_LOGIN = 2;

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

  const searchQuery = useAlertsSearchQuery(searchTerm, {
    enabled: isSearchActive,
  });

  const searchRecords = searchQuery.data?.alerts;

  const {
    data: topAlertsWeekData,
    refetch: refetchTopAlertsWeek,
    isError: topAlertsWeekError,
    isPending: topAlertsWeekPending,
  } = useDashboardTopAlertsWeekQuery({ enabled: !isSearchActive });

  const { high: mockHigh, medium: mockMedium } = useMemo(
    () => partitionAlertsByRisk(MOCK_ALERTS),
    [],
  );

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
      .slice(0, 3)
      .map(item => mapApiAlertToDashboardTopAlertWeeklyItem(item));
  }, [isSearchActive, searchRecords]);

  const topAlerts = isSearchActive
    ? topAlertsFromSearch
    : (topAlertsWeekData ?? []);

  const criticalCount = isSearchActive
    ? searchPartition.critical
    : typeof statsData?.critical_count === 'number'
      ? statsData.critical_count
      : mockHigh.length;
  const highCount = isSearchActive
    ? searchPartition.high
    : typeof statsCounts?.high === 'number'
      ? statsCounts.high
      : mockMedium.length;

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
    if (statsDataUpdatedAt > 0 && statsData && !statsError) {
      return formatDashboardUpdatedRelative(
        new Date(statsDataUpdatedAt).toISOString(),
      );
    }
    return formatDashboardUpdatedRelative(lastUpdatedIso);
  }, [
    isSearchActive,
    searchQuery.dataUpdatedAt,
    searchQuery.isError,
    statsDataUpdatedAt,
    statsData,
    statsError,
    lastUpdatedIso,
  ]);

  const metadataName = user?.user_metadata?.full_name;
  const fullName = typeof metadataName === 'string' ? metadataName : undefined;
  const email = subscriber?.email ?? user?.email ?? null;
  const firstName = deriveFirstName(fullName, email);

  const newCriticalSinceLogin = isSearchActive ? 0 : NEW_CRITICAL_SINCE_LAST_LOGIN;
  const newHighSinceLogin = isSearchActive ? 0 : NEW_HIGH_SINCE_LAST_LOGIN;
  const totalNewSinceLogin = newCriticalSinceLogin + newHighSinceLogin;

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

  function handleRefresh() {
    setLastUpdatedIso(new Date().toISOString());
    if (isSearchActive) {
      void searchQuery.refetch();
    } else {
      void refetchStats();
      void refetchTopAlertsWeek();
    }
    router.refresh();
  }

  return (
    <div className="space-y-6 lg:space-y-8">
      <DashboardWelcomeHeader
        firstName={firstName}
        newAlertsSinceLastLogin={totalNewSinceLogin}
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
          newSinceLastLogin={newCriticalSinceLogin}
        />
        <DashboardCriticalRiskCard
          label="High Risk Alerts"
          rangeLabel="71-80"
          value={highCount}
          description="Elevated risk requiring close monitoring."
          tone="high"
          icon={<AlertTriangle className="size-6 sm:size-7" aria-hidden />}
          href={alertsContinueHref.high}
          newSinceLastLogin={newHighSinceLogin}
        />
      </div>

      <DashboardIntelligenceBriefs
        briefs={DASHBOARD_MOCK_BRIEFS}
        viewAllHref="/briefs"
      />

      <DashboardRecentBriefsTable
        briefs={DASHBOARD_RECENT_BRIEFS}
        viewAllHref="/briefs"
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
