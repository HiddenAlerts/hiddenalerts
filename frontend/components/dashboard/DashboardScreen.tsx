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
import { MOCK_ALERTS } from '@/data/mockAlerts';
import { partitionAlertsByRisk } from '@/lib/alertRisk';
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
import { DashboardUnlockCta } from './DashboardUnlockCta';

function pct(part: number, total: number) {
  if (total <= 0) return 0;
  return Math.round((part / total) * 100);
}

/** Max alert rows per risk section on the dashboard (full totals still in stats / badge). */
const DASHBOARD_ALERTS_PER_RISK = 3;

export const DashboardScreen: FC = () => {
  const router = useRouter();
  const [earlyAccessOpen, setEarlyAccessOpen] = useState(false);
  const [lastUpdatedIso, setLastUpdatedIso] = useState(
    DASHBOARD_DUMMY_LAST_UPDATED_ISO,
  );

  const { high, medium, low } = useMemo(
    () => partitionAlertsByRisk(MOCK_ALERTS),
    [],
  );
  const total = MOCK_ALERTS.length;

  const highSorted = useMemo(
    () => [...high].sort((a, b) => b.occurredAt.localeCompare(a.occurredAt)),
    [high],
  );
  const mediumSorted = useMemo(
    () => [...medium].sort((a, b) => b.occurredAt.localeCompare(a.occurredAt)),
    [medium],
  );
  const lowSorted = useMemo(
    () => [...low].sort((a, b) => b.occurredAt.localeCompare(a.occurredAt)),
    [low],
  );

  const lastUpdatedLabel = formatDashboardLastUpdatedUtc(lastUpdatedIso);

  return (
    <div className="space-y-6 lg:space-y-8">
      <DashboardPageHeader
        title="Fraud Intelligence Dashboard"
        subtitle="Real-time monitoring of fraud, sanctions, and exposure signals."
        statusLine={
          <>
            <span className="text-danger font-semibold tabular-nums">
              {total}
            </span>
            <span> relevant alerts detected</span>
          </>
        }
        lastUpdatedLabel={lastUpdatedLabel}
        onViewAlerts={() => router.push('/alerts')}
        onRefresh={() => {
          setLastUpdatedIso(new Date().toISOString());
          router.refresh();
        }}
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardRiskSummaryCard
          label="High risk"
          value={high.length}
          percentOfTotal={pct(high.length, total)}
          tone="danger"
          href="/alerts?risk=high"
          icon={<ShieldAlert className="size-5 sm:size-[32px]" aria-hidden />}
        />
        <DashboardRiskSummaryCard
          label="Medium risk"
          value={medium.length}
          percentOfTotal={pct(medium.length, total)}
          tone="warning"
          href="/alerts?risk=medium"
          icon={<AlertTriangle className="size-5 sm:size-[32px]" aria-hidden />}
        />
        <DashboardRiskSummaryCard
          label="Low risk"
          value={low.length}
          percentOfTotal={pct(low.length, total)}
          tone="success"
          href="/alerts?risk=low"
          icon={<ShieldCheck className="size-5 sm:size-[32px]" aria-hidden />}
        />
        <DashboardRiskSummaryCard
          label="All alerts"
          value={total}
          percentOfTotal={total === 0 ? 0 : 100}
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
          count={highSorted.length}
          viewAllHref="/alerts?risk=high"
          riskTone="high"
          emptyMessage="No high-risk alerts."
        >
          {highSorted.slice(0, DASHBOARD_ALERTS_PER_RISK).map(alert => (
            <DashboardAlertListItem key={alert.id} alert={alert} />
          ))}
        </DashboardAlertGroup>

        <DashboardAlertGroup
          title="Medium Risk Alerts"
          count={mediumSorted.length}
          viewAllHref="/alerts?risk=medium"
          riskTone="medium"
          emptyMessage="No medium-risk alerts."
        >
          {mediumSorted.slice(0, DASHBOARD_ALERTS_PER_RISK).map(alert => (
            <DashboardAlertListItem key={alert.id} alert={alert} />
          ))}
        </DashboardAlertGroup>

        <DashboardAlertGroup
          title="Low Risk Alerts"
          count={lowSorted.length}
          viewAllHref="/alerts?risk=low"
          riskTone="low"
          emptyMessage="No low-risk alerts."
        >
          {lowSorted.slice(0, DASHBOARD_ALERTS_PER_RISK).map(alert => (
            <DashboardAlertListItem key={alert.id} alert={alert} />
          ))}
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
