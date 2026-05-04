'use client';

import { EarlyAccessModal } from '@/components/alerts/EarlyAccessModal';
import {
  DASHBOARD_DUMMY_LAST_UPDATED_ISO,
  DASHBOARD_UNLOCK_CTA,
} from '@/data/dashboardConstants';
import {
  DASHBOARD_RISK_LEGEND_INFO,
  DASHBOARD_RISK_LEGEND_ITEMS,
} from '@/data/dashboardRiskLegend';
import { DASHBOARD_TOP_ALERTS } from '@/data/dashboardTopAlerts';
import { MOCK_ALERTS } from '@/data/mockAlerts';
import { useAlertsStatsQuery } from '@/hooks/useAlertsStatsQuery';
import { useDashboardRiskPreviewsQuery } from '@/hooks/useDashboardRiskPreviewsQuery';
import { partitionAlertsByRisk } from '@/lib/alertRisk';
import { mapAlertsStatsToRiskCounts } from '@/lib/api/alerts';
import { formatDashboardLastUpdatedUtc } from '@/lib/formatDashboardDate';
import { AlertTriangle, Bell, ShieldAlert, ShieldCheck } from 'lucide-react';
import { useRouter } from 'next/navigation';
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
  const [earlyAccessOpen, setEarlyAccessOpen] = useState(false);
  const [lastUpdatedIso, setLastUpdatedIso] = useState(
    DASHBOARD_DUMMY_LAST_UPDATED_ISO,
  );

  const {
    data: statsData,
    dataUpdatedAt: statsDataUpdatedAt,
    refetch: refetchStats,
    isError: statsError,
  } = useAlertsStatsQuery('all');

  const statsCounts = useMemo(
    () =>
      statsData && !statsError ? mapAlertsStatsToRiskCounts(statsData) : null,
    [statsData, statsError],
  );

  const {
    highQuery,
    mediumQuery,
    lowQuery,
    highAlerts,
    mediumAlerts,
    lowAlerts,
    refetchAll: refetchRiskPreviews,
  } = useDashboardRiskPreviewsQuery();

  const { high, medium, low } = useMemo(
    () => partitionAlertsByRisk(MOCK_ALERTS),
    [],
  );
  const mockTotal = MOCK_ALERTS.length;

  const totalAlerts =
    typeof statsCounts?.all === 'number' ? statsCounts.all : mockTotal;
  const highTotal =
    typeof statsCounts?.high === 'number' ? statsCounts.high : high.length;
  const mediumTotal =
    typeof statsCounts?.medium === 'number'
      ? statsCounts.medium
      : medium.length;
  const lowTotal =
    typeof statsCounts?.low === 'number' ? statsCounts.low : low.length;

  const lastUpdatedLabel = useMemo(() => {
    if (statsDataUpdatedAt > 0 && statsData && !statsError) {
      return formatDashboardLastUpdatedUtc(
        new Date(statsDataUpdatedAt).toISOString(),
      );
    }
    return formatDashboardLastUpdatedUtc(lastUpdatedIso);
  }, [statsDataUpdatedAt, statsData, statsError, lastUpdatedIso]);

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
        onViewAlerts={() => router.push('/alerts')}
        onRefresh={() => {
          setLastUpdatedIso(new Date().toISOString());
          void refetchStats();
          void refetchRiskPreviews();
          router.refresh();
        }}
      />

      <DashboardTopAlertsSection
        title="Top Alerts You Should Know"
        subtitle="The highest priority alerts based on risk score and recency"
        viewAllHref="/alerts?risk=high"
        viewAllLabel="View all high risk alerts"
        riskTone="high"
        alerts={DASHBOARD_TOP_ALERTS}
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardRiskSummaryCard
          label="High risk"
          value={highTotal}
          percentOfTotal={pct(highTotal, totalAlerts)}
          tone="danger"
          href="/alerts?risk=high"
          icon={<ShieldAlert className="size-5 sm:size-[32px]" aria-hidden />}
        />
        <DashboardRiskSummaryCard
          label="Medium risk"
          value={mediumTotal}
          percentOfTotal={pct(mediumTotal, totalAlerts)}
          tone="warning"
          href="/alerts?risk=medium"
          icon={<AlertTriangle className="size-5 sm:size-[32px]" aria-hidden />}
        />
        <DashboardRiskSummaryCard
          label="Low risk"
          value={lowTotal}
          percentOfTotal={pct(lowTotal, totalAlerts)}
          tone="success"
          href="/alerts?risk=low"
          icon={<ShieldCheck className="size-5 sm:size-[32px]" aria-hidden />}
        />
        <DashboardRiskSummaryCard
          label="All alerts"
          value={totalAlerts}
          percentOfTotal={totalAlerts === 0 ? 0 : 100}
          tone="info"
          href="/alerts"
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
          viewAllHref="/alerts?risk=high"
          riskTone="high"
          emptyMessage="No high-risk alerts."
        >
          {highQuery.isPending && !highQuery.data ? (
            <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
              Loading alerts…
            </p>
          ) : (
            highAlerts.map(alert => (
              <DashboardAlertListItem key={alert.id} alert={alert} />
            ))
          )}
        </DashboardAlertGroup>

        <DashboardAlertGroup
          title="Medium Risk Alerts"
          count={mediumTotal}
          viewAllHref="/alerts?risk=medium"
          riskTone="medium"
          emptyMessage="No medium-risk alerts."
        >
          {mediumQuery.isPending && !mediumQuery.data ? (
            <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
              Loading alerts…
            </p>
          ) : (
            mediumAlerts.map(alert => (
              <DashboardAlertListItem key={alert.id} alert={alert} />
            ))
          )}
        </DashboardAlertGroup>

        <DashboardAlertGroup
          title="Low Risk Alerts"
          count={lowTotal}
          viewAllHref="/alerts?risk=low"
          riskTone="low"
          emptyMessage="No low-risk alerts."
          collapsible
          defaultCollapsed
          collapsedSummary="Low risk alerts are collapsed by default"
        >
          {lowQuery.isPending && !lowQuery.data ? (
            <p className="text-muted border-border rounded-lg border border-dashed px-4 py-8 text-center text-sm">
              Loading alerts…
            </p>
          ) : (
            lowAlerts.map(alert => (
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
