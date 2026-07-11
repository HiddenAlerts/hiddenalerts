import type { AlertsRiskFilterValue } from '@/data/alertRiskFilterOptions';
import {
  formatRiskLevelLabel,
  getRiskBandBadgeLabel,
  simplifyAlertSourceName,
} from '@/lib/alertDisplay';
import type { AlertBadgeTone, AlertItem } from '@/types/alert';
import type {
  AlertApiRecord,
  AlertDetailApiRecord,
  AlertsListResponse,
  AlertsSearchResponse,
  AlertsStatsResponse,
} from '@/types/alertsApi';

import { apiGet } from './client';

export const ALERTS_PAGE_SIZE = 20;

/**
 * All endpoints below now go through the authenticated subscriber API.
 * The Supabase access token must be passed by the caller. Hooks read it
 * from `useAuth()` and only run when the token is available.
 */
const SUBSCRIBER_BASE = '/v1/subscriber';

export type FetchAlertsParams = {
  limit: number;
  offset: number;
  category?: string;
  risk_level?: string;
  source?: string;
};

function riskBandToBadgeTone(riskBand?: string | null): AlertBadgeTone {
  const band = riskBand?.trim().toLowerCase();
  if (band === 'critical' || band === 'high') return 'danger';
  return 'info';
}

function riskLevelToBadge(risk: string): AlertBadgeTone {
  const r = risk.toLowerCase();
  if (r === 'high') return 'danger';
  if (r === 'medium') return 'warning';
  if (r === 'low') return 'success';
  return 'info';
}

export function mapApiAlertToAlertItem(record: AlertApiRecord): AlertItem {
  const matchedRaw = record.matched_entity;
  const matchedEntity =
    typeof matchedRaw === 'string' && matchedRaw.trim().length > 0
      ? matchedRaw.trim()
      : undefined;

  const riskBandLabel = getRiskBandBadgeLabel(record.risk_band);

  return {
    id: String(record.id),
    title: record.title,
    description: record.summary,
    sourceLabel: record.source_name,
    sourceDisplayLabel: simplifyAlertSourceName(record.source_name),
    badgeTone: riskBandLabel
      ? riskBandToBadgeTone(record.risk_band)
      : riskLevelToBadge(record.risk_level),
    riskLevelLabel: formatRiskLevelLabel(record.risk_level),
    riskBandLabel,
    riskBand: record.risk_band,
    signalScore: record.signal_score,
    sourceUrl: record.source_url,
    category: record.category,
    occurredAt: record.published_at,
    sourcePublishedAt:
      typeof record.source_published_at === 'string' &&
      record.source_published_at.trim().length > 0
        ? record.source_published_at.trim()
        : undefined,
    ...(matchedEntity !== undefined ? { matchedEntity } : {}),
  };
}

export function buildAlertsListPath(params: FetchAlertsParams) {
  const search = new URLSearchParams();
  search.set('limit', String(params.limit));
  search.set('offset', String(params.offset));
  if (params.category) search.set('category', params.category);
  if (params.risk_level) search.set('risk_level', params.risk_level);
  if (params.source) search.set('source', params.source);
  return `${SUBSCRIBER_BASE}/alerts?${search.toString()}`;
}

export function buildAlertDetailPath(alertId: string) {
  return `${SUBSCRIBER_BASE}/alerts/${encodeURIComponent(alertId)}`;
}

export async function fetchAlertsPage(
  params: FetchAlertsParams,
  token: string,
): Promise<AlertsListResponse> {
  return apiGet<AlertsListResponse>(buildAlertsListPath(params), { token });
}

export async function fetchAlertDetail(
  alertId: string,
  token: string,
): Promise<AlertDetailApiRecord> {
  return apiGet<AlertDetailApiRecord>(buildAlertDetailPath(alertId), { token });
}

export function buildTopAlertsPath() {
  return `${SUBSCRIBER_BASE}/alerts/top`;
}

export async function fetchTopAlerts(
  token: string,
): Promise<AlertsListResponse> {
  return apiGet<AlertsListResponse>(buildTopAlertsPath(), { token });
}

export type FetchAlertsStatsParams = {
  /** When set and not `all`, forwarded as `category` query param if the API supports scoped stats. */
  category?: string;
};

export function buildAlertsStatsPath(params?: FetchAlertsStatsParams): string {
  const search = new URLSearchParams();
  const cat = params?.category?.trim();
  if (cat && cat !== 'all') {
    search.set('category', cat);
  }
  const qs = search.toString();
  return qs
    ? `${SUBSCRIBER_BASE}/alerts/stats?${qs}`
    : `${SUBSCRIBER_BASE}/alerts/stats`;
}

export async function fetchAlertsStats(
  token: string,
  params?: FetchAlertsStatsParams,
): Promise<AlertsStatsResponse> {
  return apiGet<AlertsStatsResponse>(buildAlertsStatsPath(params), { token });
}

export type FetchAlertsSearchParams = {
  q: string;
  min_score?: number;
  limit?: number;
  group_limit?: number;
};

/** Builds path for `GET /v1/subscriber/search/alerts`. */
export function buildAlertsSearchPath(params: FetchAlertsSearchParams): string {
  const q = params.q.trim();
  const searchParams = new URLSearchParams({
    q,
    min_score: String(params.min_score ?? 0),
    limit: String(params.limit ?? 50),
    group_limit: String(params.group_limit ?? 20),
  });
  return `${SUBSCRIBER_BASE}/search/alerts?${searchParams.toString()}`;
}

export async function fetchAlertsSearch(
  params: FetchAlertsSearchParams,
  token: string,
): Promise<AlertsSearchResponse> {
  const q = params.q.trim();
  if (!q) {
    return {
      query: '',
      normalized_query: '',
      total_alerts: 0,
      group_count: 0,
      groups: [],
      alerts: [],
    };
  }
  return apiGet<AlertsSearchResponse>(buildAlertsSearchPath(params), { token });
}

/** Maps `/alerts/stats` payload to risk tab counts. */
export function mapAlertsStatsToRiskCounts(
  data: AlertsStatsResponse,
): Record<AlertsRiskFilterValue, number> {
  return {
    all: data.total_alerts,
    high: data.high_count,
    medium: data.medium_count,
    low: data.low_count,
  };
}
