import { categoryToCoverTheme } from '@/lib/briefDetail';
import { resolveBriefRiskLabel } from '@/lib/briefs';
import { stripHtmlToText } from '@/lib/htmlText';
import { keySignalsArrayToHtml } from '@/lib/keySignalsFormat';
import type { BriefDetail, BriefDetailRiskLevel, SubscriberBrief } from '@/types/briefs';
import type {
  SubscriberBriefDetailApi,
  SubscriberBriefListItemApi,
  SubscriberBriefListResponse,
} from '@/types/subscriberBriefsApi';

import { resolveAssetUrl } from './assetUrl';
import { apiGet, type HttpRequestError } from './client';

/**
 * All endpoints below are the authenticated subscriber API. The Supabase
 * access token must be passed by the caller — hooks read it from `useAuth()`.
 */
const SUBSCRIBER_BRIEFS_BASE = '/v1/subscriber/intelligence-briefs';

export const SUBSCRIBER_BRIEFS_PAGE_SIZE = 8;

/** Max the backend allows per page — used for the bulk facets/stats fetch. */
export const SUBSCRIBER_BRIEFS_OVERVIEW_LIMIT = 100;

function riskLevelToDetailRiskLevel(level: string | null): BriefDetailRiskLevel {
  const normalized = level?.trim().toLowerCase();
  if (
    normalized === 'critical' ||
    normalized === 'high' ||
    normalized === 'medium' ||
    normalized === 'low'
  ) {
    return normalized;
  }
  return 'unknown';
}

/** Pass through API score; null → 0 only as a typed sentinel (UI shows "—" for ≤0). */
function mapRiskScore(score: number | null | undefined): number {
  return typeof score === 'number' && Number.isFinite(score) ? score : 0;
}

export function mapApiListItemToSubscriberBrief(
  record: SubscriberBriefListItemApi,
): SubscriberBrief {
  const riskScore = mapRiskScore(record.risk_score);
  const riskLevel = riskLevelToDetailRiskLevel(record.risk_level);
  return {
    id: String(record.id),
    slug: record.slug,
    title: record.title,
    category: record.category ?? '',
    coverageAreas: record.tags ?? [],
    date: record.published_at ? record.published_at.slice(0, 10) : '',
    riskScore,
    riskLabel: resolveBriefRiskLabel(riskLevel),
    coverTheme: categoryToCoverTheme(record.category ?? ''),
    featuredImage: resolveAssetUrl(record.featured_image_url),
    sourceCount: record.alerts_count,
    featured: record.is_featured,
    summary: stripHtmlToText(record.executive_summary ?? ''),
    href: `/briefs/${record.slug}`,
  };
}

/** Maps the `/featured` detail payload down to the lightweight card shape. */
export function mapApiDetailToSubscriberBriefCard(
  record: SubscriberBriefDetailApi,
): SubscriberBrief {
  const riskScore = mapRiskScore(record.risk_score);
  const riskLevel = riskLevelToDetailRiskLevel(record.risk_level);
  return {
    id: String(record.id),
    slug: record.slug,
    title: record.title,
    category: record.category ?? '',
    coverageAreas: record.tags ?? [],
    date: record.published_at ? record.published_at.slice(0, 10) : '',
    riskScore,
    riskLabel: resolveBriefRiskLabel(riskLevel),
    coverTheme: categoryToCoverTheme(record.category ?? ''),
    featuredImage: resolveAssetUrl(record.featured_image_url),
    sourceCount: record.alerts_count,
    featured: record.is_featured,
    summary: stripHtmlToText(record.executive_summary ?? ''),
    href: `/briefs/${record.slug}`,
  };
}

export function mapApiDetailToBriefDetail(record: SubscriberBriefDetailApi): BriefDetail {
  const riskScore = mapRiskScore(record.risk_score);
  const riskLevel = riskLevelToDetailRiskLevel(record.risk_level);
  return {
    id: String(record.id),
    slug: record.slug,
    title: record.title,
    category: record.category ?? '',
    coverTheme: categoryToCoverTheme(record.category ?? ''),
    riskScore,
    riskLevel,
    confidenceLevel:
      record.confidence_level === 'high' || record.confidence_level === 'low'
        ? record.confidence_level
        : 'medium',
    primaryEntities: record.primary_entities ?? [],
    tags: record.tags ?? [],
    featuredImage: resolveAssetUrl(record.featured_image_url),
    executiveSummary: record.executive_summary ?? '',
    whyThisMatters: record.why_this_matters ?? '',
    keySignals: keySignalsArrayToHtml(record.key_signals ?? []),
    riskAssessment: record.risk_assessment ?? '',
    whatOthersMiss: record.what_others_miss ?? '',
    implications: record.implications ?? '',
    mainBrief: record.main_intelligence_brief ?? '',
    supportingAlerts: (record.supporting_alerts ?? []).map(a => ({
      url: a.url,
      title: a.title ?? undefined,
    })),
    // Subscriber endpoints only ever return published, visible briefs.
    status: 'published',
    publishedDate: record.published_at ?? undefined,
  };
}

export type FetchSubscriberBriefsParams = {
  q?: string;
  category?: string;
  risk_level?: string;
  limit?: number;
  offset?: number;
};

export function buildSubscriberBriefsListPath(params: FetchSubscriberBriefsParams) {
  const search = new URLSearchParams();
  if (params.q) search.set('q', params.q);
  if (params.category) search.set('category', params.category);
  if (params.risk_level) search.set('risk_level', params.risk_level);
  search.set('limit', String(params.limit ?? SUBSCRIBER_BRIEFS_PAGE_SIZE));
  search.set('offset', String(params.offset ?? 0));
  return `${SUBSCRIBER_BRIEFS_BASE}?${search.toString()}`;
}

export async function fetchSubscriberBriefsPage(
  params: FetchSubscriberBriefsParams,
  token: string,
): Promise<{ items: SubscriberBrief[]; total: number; limit: number; offset: number }> {
  const res = await apiGet<SubscriberBriefListResponse>(
    buildSubscriberBriefsListPath(params),
    { token },
  );
  return { ...res, items: res.items.map(mapApiListItemToSubscriberBrief) };
}

/**
 * The list endpoint's `total` is exact regardless of `limit` — so an exact
 * count for any filter combination is just a `limit=1` fetch that discards
 * `items` and reads `total`. Used to build accurate stats/category counts
 * without needing a dedicated aggregates endpoint.
 */
export async function fetchSubscriberBriefsCount(
  params: Omit<FetchSubscriberBriefsParams, 'limit' | 'offset'>,
  token: string,
): Promise<number> {
  const res = await apiGet<SubscriberBriefListResponse>(
    buildSubscriberBriefsListPath({ ...params, limit: 1, offset: 0 }),
    { token },
  );
  return res.total;
}

/**
 * Returns `null` (not `undefined` — React Query rejects `undefined` query
 * results) when no brief is currently featured.
 */
export async function fetchFeaturedSubscriberBrief(
  token: string,
): Promise<SubscriberBrief | null> {
  try {
    const record = await apiGet<SubscriberBriefDetailApi>(
      `${SUBSCRIBER_BRIEFS_BASE}/featured`,
      { token },
    );
    return mapApiDetailToSubscriberBriefCard(record);
  } catch (err) {
    if ((err as HttpRequestError).status === 404) return null;
    throw err;
  }
}

export async function fetchSubscriberBriefBySlug(
  slug: string,
  token: string,
): Promise<BriefDetail> {
  const record = await apiGet<SubscriberBriefDetailApi>(
    `${SUBSCRIBER_BRIEFS_BASE}/${encodeURIComponent(slug)}`,
    { token },
  );
  return mapApiDetailToBriefDetail(record);
}
