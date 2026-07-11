import type { AdminAlert, AdminAlertDetail, AdminAlertRiskExplanation } from '@/types/admin';
import type {
  AdminAlertApiRecord,
  AdminAlertDetailApiRecord,
  AdminAlertReviewApiRecord,
  AdminAlertReviewPayload,
  AdminAlertRiskExplanationApi,
} from '@/types/adminAlertsApi';

import { apiGet, apiPost } from './client';

/**
 * Admin alerts — authenticated with the backend JWT from
 * `lib/auth/adminSession`'s `getAdminToken()`.
 */
const ALERTS_BASE = '/v1/alerts';

export function buildAdminAlertPath(alertId: string) {
  return `${ALERTS_BASE}/${encodeURIComponent(alertId)}`;
}

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

function mapRiskExplanation(
  record: AdminAlertRiskExplanationApi,
): AdminAlertRiskExplanation {
  return {
    scoreTotal: record.score_total,
    score100: record.score_100,
    riskLevel: record.risk_level,
    riskBand: record.risk_band,
    factors: {
      sourceCredibility: record.factors.source_credibility,
      financialImpact: record.factors.financial_impact,
      victimScale: record.factors.victim_scale,
      crossSource: record.factors.cross_source,
      trendAcceleration: record.factors.trend_acceleration,
    },
    publicationDecision: record.publication_decision,
    publicationReason: record.publication_reason ?? undefined,
    pendingReviewReason: record.pending_review_reason ?? undefined,
    source: record.source,
    sourceCredibility: record.source_credibility,
  };
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

export function mapApiAlertDetailToAdminAlertDetail(
  record: AdminAlertDetailApiRecord,
): AdminAlertDetail {
  const date =
    record.source_published_at ??
    record.processed_at ??
    record.published_at ??
    '';

  return {
    id: String(record.id),
    title: record.title,
    sourceName: record.source_name,
    itemUrl: record.item_url,
    riskScore: record.signal_score_total ?? 0,
    riskLevel: record.risk_level,
    riskBand: record.risk_band,
    category: record.primary_category ?? '',
    secondaryCategory: record.secondary_category ?? undefined,
    date,
    processedAt: record.processed_at,
    publishedAt: record.published_at ?? undefined,
    summary: record.summary?.trim() ?? '',
    tags: record.matched_keywords ?? [],
    status: record.is_published ? 'published' : 'draft',
    publishDecision: record.publish_decision,
    publishDecisionReason: record.publish_decision_reason ?? undefined,
    pendingReviewReason: record.pending_review_reason ?? undefined,
    isExcluded: record.is_excluded,
    excludedReason: record.excluded_reason ?? undefined,
    isManualHold: record.is_manual_hold,
    publishedByRule: record.published_by_rule,
    publicationStateSource: record.publication_state_source ?? undefined,
    publicationStateUpdatedAt: record.publication_state_updated_at ?? undefined,
    publishingPolicyVersion: record.publishing_policy_version ?? undefined,
    reviewStatus: record.review_status ?? undefined,
    eventId: record.event_id ?? undefined,
    eventTitle: record.event_title ?? undefined,
    financialImpactEstimate: record.financial_impact_estimate ?? undefined,
    victimScaleRaw: record.victim_scale_raw ?? undefined,
    scoreBreakdown: {
      sourceCredibility: record.score_source_credibility ?? undefined,
      financialImpact: record.score_financial_impact ?? undefined,
      victimScale: record.score_victim_scale ?? undefined,
      crossSource: record.score_cross_source ?? undefined,
      trendAcceleration: record.score_trend_acceleration ?? undefined,
    },
    riskExplanation: record.risk_explanation
      ? mapRiskExplanation(record.risk_explanation)
      : undefined,
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

export async function fetchAdminAlertDetail(
  alertId: string,
  token: string,
): Promise<AdminAlertDetail> {
  const record = await apiGet<AdminAlertDetailApiRecord>(
    buildAdminAlertPath(alertId),
    { token },
  );
  return mapApiAlertDetailToAdminAlertDetail(record);
}

export async function submitAdminAlertReview(
  alertId: string,
  payload: AdminAlertReviewPayload,
  token: string,
): Promise<AdminAlertReviewApiRecord> {
  return apiPost<AdminAlertReviewApiRecord>(
    `${buildAdminAlertPath(alertId)}/review`,
    payload,
    { token },
  );
}
