'use client';

import {
  AlertsSearchForm,
  AlertsSearchFormFallback,
} from '@/components/alerts/AlertsSearchForm';
import { useAuth } from '@/contexts/AuthProvider';
import { DASHBOARD_DUMMY_LAST_UPDATED_ISO } from '@/data/dashboardConstants';
import { DASHBOARD_MOCK_BRIEFS } from '@/data/dashboardBriefs';
import { DASHBOARD_RECENT_BRIEFS } from '@/data/dashboardRecentBriefs';
import { DASHBOARD_TOP_ALERTS_THIS_WEEK } from '@/data/dashboardTopAlertsThisWeek';
import { MOCK_ALERTS } from '@/data/mockAlerts';
import { useAlertsSearchQuery } from '@/hooks/useAlertsSearchQuery';
import { useAlertsStatsQuery } from '@/hooks/useAlertsStatsQuery';
import { partitionAlertsByRisk } from '@/lib/alertRisk';
import {
  mapAlertsStatsToRiskCounts,
  mapApiAlertToAlertItem,
} from '@/lib/api/alerts';
import { buildAlertsListQueryString } from '@/lib/alertsUrlState';
import { formatDashboardUpdatedRelative } from '@/lib/formatDashboardDate';
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

  const { high: mockHigh, medium: mockMedium } = useMemo(
    () => partitionAlertsByRisk(MOCK_ALERTS),
    [],
  );

  const searchPartition = useMemo(() => {
    if (!isSearchActive || !searchRecords) {
      return { high: [], medium: [], low: [] };
    }
    return partitionAlertsByRisk(searchRecords.map(mapApiAlertToAlertItem));
  }, [isSearchActive, searchRecords]);

  const criticalCount = isSearchActive
    ? searchPartition.high.length
    : typeof statsCounts?.high === 'number'
      ? statsCounts.high
      : mockHigh.length;
  const highCount = isSearchActive
    ? searchPartition.medium.length
    : typeof statsCounts?.medium === 'number'
      ? statsCounts.medium
      : mockMedium.length;

  const alertsContinueHref = useMemo(() => {
    const q = isSearchActive ? searchTerm : undefined;
    const qs = (risk: string) =>
      buildAlertsListQueryString(risk, 1, 'all', q);
    const allQs = buildAlertsListQueryString('all', 1, 'all', q);
    return {
      critical: qs('high') ? `/alerts?${qs('high')}` : '/alerts',
      high: qs('medium') ? `/alerts?${qs('medium')}` : '/alerts',
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

  function handleRefresh() {
    setLastUpdatedIso(new Date().toISOString());
    if (isSearchActive) {
      void searchQuery.refetch();
    } else {
      void refetchStats();
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
          rangeLabel="80-100"
          value={criticalCount}
          description="Immediate attention required."
          tone="critical"
          icon={<ShieldAlert className="size-6 sm:size-7" aria-hidden />}
          href={alertsContinueHref.critical}
          newSinceLastLogin={newCriticalSinceLogin}
        />
        <DashboardCriticalRiskCard
          label="High Risk Alerts"
          rangeLabel="60-79"
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
        viewAllHref="/alerts"
      />

      <DashboardRecentBriefsTable
        briefs={DASHBOARD_RECENT_BRIEFS}
        viewAllHref="/alerts"
      />

      <DashboardTopAlertsThisWeek
        alerts={DASHBOARD_TOP_ALERTS_THIS_WEEK}
        viewAllHref={alertsContinueHref.all}
        viewAllLabel="View all alerts"
      />
    </div>
  );
};
