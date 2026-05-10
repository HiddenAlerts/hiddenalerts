import type {
  DashboardTopAlertIconVariant,
  DashboardTopAlertItem,
} from '@/data/dashboardTopAlerts';
import type { AlertApiRecord } from '@/types/alertsApi';

export function mapCategoryToDashboardTopIconVariant(
  category: string,
): DashboardTopAlertIconVariant {
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

export function mapApiAlertToDashboardTopAlertItem(
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
    iconVariant: mapCategoryToDashboardTopIconVariant(record.category),
  };
}
