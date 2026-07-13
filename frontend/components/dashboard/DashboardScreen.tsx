'use client';

import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/contexts/AuthProvider';
import {
  DASHBOARD_SEARCH_ALERTS_LIMIT,
  DASHBOARD_SEARCH_GROUP_LIMIT,
  DASHBOARD_TOP_ALERTS_WEEK_LIMIT,
  useAlertsSearchQuery,
  useDashboardBriefsPreviewQuery,
  useDashboardTopAlertsWeekQuery,
} from '@/hooks';
import { buildAlertsListQueryString } from '@/lib/alertsUrlState';
import { pickNewestCriticalHighAlerts } from '@/lib/dashboardAlerts';
import { formatDashboardUpdatedRelative } from '@/lib/formatDashboardDate';
import { mapApiAlertToDashboardTopAlertWeeklyItem } from '@/lib/mapApiAlertToDashboardTopAlertWeekly';
import { useRouter, useSearchParams } from 'next/navigation';
import type { FC } from 'react';
import { useMemo } from 'react';

import { DashboardCoverageAreas } from './DashboardCoverageAreas';
import { DashboardIntelligenceBriefs } from './DashboardIntelligenceBriefs';
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

/**
 * Subscriber dashboard aligned to Ken’s revised mockup:
 * Welcome → Featured Briefs → Top Alerts (Critical/High) → Coverage Areas
 */
export const DashboardScreen: FC = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, subscriber } = useAuth();
  const searchQueryRaw = searchParams.get('q') ?? '';
  const searchTerm = searchQueryRaw.trim();
  const isSearchActive = searchTerm.length > 0;

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

  const topAlertsFromSearch = useMemo(() => {
    if (!isSearchActive || !searchRecords?.length) return [];
    const now = Date.now();
    return pickNewestCriticalHighAlerts(
      searchRecords,
      DASHBOARD_TOP_ALERTS_WEEK_LIMIT,
    ).map(item => mapApiAlertToDashboardTopAlertWeeklyItem(item, now));
  }, [isSearchActive, searchRecords]);

  const topAlerts = isSearchActive
    ? topAlertsFromSearch
    : (topAlertsWeekData ?? []);

  const alertsContinueHref = useMemo(() => {
    const q = isSearchActive ? searchTerm : undefined;
    const allQs = buildAlertsListQueryString('all', 1, 'all', q);
    return allQs ? `/alerts?${allQs}` : '/alerts';
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
        subtitle="Your fraud intelligence overview."
        lastUpdatedLabel={lastUpdatedLabel}
        onRefresh={handleRefresh}
      />

      <DashboardIntelligenceBriefs
        briefs={dashboardBriefs}
        viewAllHref="/briefs"
        bodyContent={briefsBodyContent}
      />

      <DashboardTopAlertsThisWeek
        title="Top Alerts This Week"
        subtitle="Critical & High only — newest first."
        alerts={topAlerts}
        viewAllHref={alertsContinueHref}
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
                isSearchActive
                  ? 'No matching alerts'
                  : 'No Critical or High alerts yet'
              }
              description={
                isSearchActive
                  ? 'No Critical or High-Risk alerts match your search right now.'
                  : 'Newest Critical and High-Risk alerts will appear here when available.'
              }
              className="py-10"
            />
          ) : undefined
        }
      />

      {!isSearchActive ? <DashboardCoverageAreas /> : null}
    </div>
  );
};
