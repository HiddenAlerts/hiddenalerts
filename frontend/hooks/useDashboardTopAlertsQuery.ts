'use client';

import type {
  DashboardTopAlertIconVariant,
  DashboardTopAlertItem,
} from '@/data/dashboardTopAlerts';
import { fetchTopAlerts } from '@/lib/api/alerts';
import type { AlertApiRecord } from '@/types/alertsApi';
import { useQuery } from '@tanstack/react-query';

export function dashboardTopAlertsQueryKey() {
  return ['alerts', 'dashboard', 'top'] as const;
}

function mapCategoryToIconVariant(category: string): DashboardTopAlertIconVariant {
  const normalized = category.trim().toLowerCase();
  if (
    normalized.includes('money') ||
    normalized.includes('crypto') ||
    normalized.includes('finance')
  ) {
    return 'wallet';
  }
  if (
    normalized.includes('sanction') ||
    normalized.includes('bribery') ||
    normalized.includes('fraud')
  ) {
    return 'landmark';
  }
  return 'user-lock';
}

function mapApiAlertToTopAlertItem(
  record: AlertApiRecord,
  index: number,
): DashboardTopAlertItem {
  return {
    id: String(record.id),
    rank: index + 1,
    score: record.signal_score,
    title: record.title,
    tags: [
      { text: record.category || 'General', tone: 'info' },
      { text: record.source_name || 'Unknown source' },
    ],
    description: record.summary,
    occurredAt: record.source_published_at || record.published_at,
    iconVariant: mapCategoryToIconVariant(record.category),
  };
}

export function useDashboardTopAlertsQuery() {
  return useQuery({
    queryKey: dashboardTopAlertsQueryKey(),
    queryFn: fetchTopAlerts,
    select: data =>
      (data.alerts ?? [])
        .slice(0, 3)
        .map((item, index) => mapApiAlertToTopAlertItem(item, index)),
    staleTime: 60_000,
  });
}
