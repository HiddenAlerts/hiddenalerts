import type { AdminAlert } from '@/types/admin';
import type { AdminAlertApiRecord } from '@/types/adminAlertsApi';

import { apiGet } from './client';

/**
 * Admin alerts list — authenticated with the backend JWT from
 * `lib/auth/adminSession`'s `getAdminToken()`.
 */
const ALERTS_BASE = '/v1/alerts';

export type FetchAdminAlertsParams = {
  keyword?: string;
  category?: string;
  risk_level?: string;
  risk_band?: string;
  is_published?: boolean;
  limit?: number;
  offset?: number;
};

export function buildAdminAlertsListPath(params: FetchAdminAlertsParams) {
  const search = new URLSearchParams();
  if (params.keyword) search.set('keyword', params.keyword);
  if (params.category) search.set('category', params.category);
  if (params.risk_level) search.set('risk_level', params.risk_level);
  if (params.risk_band) search.set('risk_band', params.risk_band);
  if (params.is_published !== undefined) {
    search.set('is_published', String(params.is_published));
  }
  search.set('limit', String(params.limit ?? 50));
  search.set('offset', String(params.offset ?? 0));
  return `${ALERTS_BASE}?${search.toString()}`;
}

export function mapApiAlertToAdminAlert(record: AdminAlertApiRecord): AdminAlert {
  const date =
    record.source_published_at ??
    record.processed_at ??
    record.published_at ??
    '';

  return {
    id: String(record.id),
    title: record.title,
    riskScore: record.signal_score_total ?? 0,
    category: record.primary_category ?? '',
    date,
    summary: record.publish_decision_reason ?? '',
    tags: record.matched_keywords ?? [],
    status: record.is_published ? 'published' : 'draft',
  };
}

export type AdminAlertsPageResult = {
  items: AdminAlert[];
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
};

/**
 * Fetches one extra row to detect whether another page exists, since the list
 * endpoint returns an array without a total count.
 */
export async function fetchAdminAlertsPage(
  params: FetchAdminAlertsParams,
  token: string,
): Promise<AdminAlertsPageResult> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;
  const records = await apiGet<AdminAlertApiRecord[]>(
    buildAdminAlertsListPath({ ...params, limit: limit + 1, offset }),
    { token },
  );

  const hasMore = records.length > limit;
  const pageRecords = records.slice(0, limit);
  const items = pageRecords.map(mapApiAlertToAdminAlert);
  const total = hasMore ? offset + items.length + 1 : offset + items.length;

  return { items, total, limit, offset, hasMore };
}
