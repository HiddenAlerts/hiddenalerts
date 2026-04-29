import {
  formatRiskLevelLabel,
  simplifyAlertSourceName,
} from '@/lib/alertDisplay';
import type { AlertBadgeTone, AlertItem } from '@/types/alert';
import type { AlertApiRecord, AlertsListResponse } from '@/types/alertsApi';

import { apiGet } from './client';

export const ALERTS_PAGE_SIZE = 20;

export type FetchAlertsParams = {
  limit: number;
  offset: number;
  category?: string;
  risk_level?: string;
  source?: string;
};

function riskLevelToBadge(risk: string): AlertBadgeTone {
  const r = risk.toLowerCase();
  if (r === 'high') return 'danger';
  if (r === 'medium') return 'warning';
  if (r === 'low') return 'success';
  return 'info';
}

export function mapApiAlertToAlertItem(record: AlertApiRecord): AlertItem {
  return {
    id: String(record.id),
    title: record.title,
    description: record.summary,
    sourceLabel: record.source_name,
    sourceDisplayLabel: simplifyAlertSourceName(record.source_name),
    badgeTone: riskLevelToBadge(record.risk_level),
    riskLevelLabel: formatRiskLevelLabel(record.risk_level),
    signalScore: record.signal_score,
    sourceUrl: record.source_url,
    category: record.category,
    occurredAt: record.published_at,
  };
}

export function buildAlertsListPath(params: FetchAlertsParams) {
  const search = new URLSearchParams();
  search.set('limit', String(params.limit));
  search.set('offset', String(params.offset));
  if (params.category) search.set('category', params.category);
  if (params.risk_level) search.set('risk_level', params.risk_level);
  if (params.source) search.set('source', params.source);
  return `/alerts?${search.toString()}`;
}

export function buildAlertDetailPath(alertId: string) {
  return `/alerts/${encodeURIComponent(alertId)}`;
}

export async function fetchAlertsPage(
  params: FetchAlertsParams,
): Promise<AlertsListResponse> {
  return apiGet<AlertsListResponse>(buildAlertsListPath(params));
}

export async function fetchAlertDetail(alertId: string): Promise<AlertApiRecord> {
  return apiGet<AlertApiRecord>(buildAlertDetailPath(alertId));
}
