'use client';

import { Button } from '@/components';
import { MOCK_ALERTS } from '@/data/mockAlerts';
import { partitionAlertsByRisk } from '@/lib/alertRisk';
import { cn } from '@/lib/utils';
import { Bell, RefreshCw, Zap } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { FC } from 'react';
import { useMemo } from 'react';

import { DashboardRiskTable } from './DashboardRiskTable';
import { DashboardStatCard } from './DashboardStatCard';

export const DashboardScreen: FC = () => {
  const router = useRouter();
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

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <h1 className="font-heading text-foreground flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Bell
              className="text-danger size-7 shrink-0"
              aria-hidden
            />
            <span>Fraud intelligence alerts</span>
          </h1>
          <p className="text-muted text-sm">
            {total} relevant alerts total — open{' '}
            <Link
              href="/alerts"
              className="text-primary-400 hover:text-primary-300 font-medium underline-offset-2 hover:underline"
            >
              Alerts
            </Link>{' '}
            for filters and pagination.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 sm:justify-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            leftIcon={<Zap className="size-4" aria-hidden />}
            onClick={() => router.push('/alerts')}
          >
            View Alerts
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            leftIcon={<RefreshCw className="size-4" aria-hidden />}
            onClick={() => router.refresh()}
          >
            Refresh
          </Button>
        </div>
      </div>

      <div
        className={cn(
          'grid gap-3 sm:grid-cols-2 lg:grid-cols-4',
        )}
      >
        <DashboardStatCard label="High risk" value={high.length} tone="danger" />
        <DashboardStatCard
          label="Medium risk"
          value={medium.length}
          tone="warning"
        />
        <DashboardStatCard label="Low risk" value={low.length} tone="muted" />
        <DashboardStatCard label="All alerts" value={total} tone="primary" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2 lg:gap-8">
        <DashboardRiskTable
          title="High risk"
          count={highSorted.length}
          alerts={highSorted}
          emptyMessage="No high-risk alerts."
        />
        <DashboardRiskTable
          title="Medium risk"
          count={mediumSorted.length}
          alerts={mediumSorted}
          emptyMessage="No medium-risk alerts."
        />
      </div>
    </div>
  );
};
