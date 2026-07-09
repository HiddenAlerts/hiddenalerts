import { keySignalsArrayToHtml, keySignalsHtmlToArray } from '@/lib/keySignalsFormat';
import type {
  AdminBrief,
  AdminBriefListItem,
  AdminConfidenceLevel,
  AdminPublishStatus,
  AdminRiskLevel,
  AdminTimeHorizon,
} from '@/types/admin';
import type {
  AdminBriefApiRecord,
  AdminBriefListItemApi,
  AdminBriefListResponse,
  BriefWritePayload,
  CreateBriefPayload,
  UpdateBriefPayload,
} from '@/types/adminBriefsApi';

import { apiDelete, apiGet, apiPost, apiPut, apiRequest } from './client';

/**
 * All endpoints below go through the authenticated admin API. The backend
 * JWT (`lib/auth/adminSession`'s `getAdminToken()`) must be passed by the
 * caller — see `hooks/useAdminBriefsListQuery.ts` etc.
 */
const ADMIN_BASE = '/v1/admin/intelligence-briefs';

export function buildAdminBriefPath(id: string) {
  return `${ADMIN_BASE}/${encodeURIComponent(id)}`;
}

export type FetchAdminBriefsParams = {
  q?: string;
  status?: string;
  category?: string;
  risk_level?: string;
  limit?: number;
  offset?: number;
};

export function buildAdminBriefsListPath(params: FetchAdminBriefsParams) {
  const search = new URLSearchParams();
  if (params.q) search.set('q', params.q);
  if (params.status) search.set('status', params.status);
  if (params.category) search.set('category', params.category);
  if (params.risk_level) search.set('risk_level', params.risk_level);
  search.set('limit', String(params.limit ?? 50));
  search.set('offset', String(params.offset ?? 0));
  return `${ADMIN_BASE}?${search.toString()}`;
}

export function mapApiBriefToAdminBrief(record: AdminBriefApiRecord): AdminBrief {
  return {
    id: String(record.id),
    briefCode: record.brief_code,
    title: record.title,
    slug: record.slug,
    category: record.category ?? '',
    riskScore: record.risk_score ?? 0,
    riskLevel: (record.risk_level as AdminRiskLevel | null) ?? 'low',
    timeHorizon: (record.time_horizon as AdminTimeHorizon | null) ?? undefined,
    primaryEntities: record.primary_entities ?? [],
    tags: record.tags ?? [],
    featuredImage: record.featured_image_url ?? undefined,
    executiveSummary: record.executive_summary ?? '',
    whyThisMatters: record.why_this_matters ?? '',
    keySignals: keySignalsArrayToHtml(record.key_signals ?? []),
    riskAssessment: record.risk_assessment ?? '',
    whatOthersMiss: record.what_others_miss ?? '',
    implications: record.implications ?? '',
    mainBrief: record.main_intelligence_brief ?? '',
    analystNotes: record.analyst_notes ?? '',
    confidenceLevel: (record.confidence_level as AdminConfidenceLevel | null) ?? 'medium',
    supportingAlerts: (record.supporting_alerts ?? []).map(a => ({
      url: a.url,
      title: a.title ?? undefined,
    })),
    featured: record.is_featured,
    isPremium: record.is_premium,
    status: record.status as AdminPublishStatus,
    alertsCount: record.alerts_count,
    readTimeMinutes: record.read_time_minutes,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    publishedDate: record.published_at ?? undefined,
  };
}

export function mapApiBriefListItemToAdminBriefListItem(
  record: AdminBriefListItemApi,
): AdminBriefListItem {
  return {
    id: String(record.id),
    briefCode: record.brief_code,
    title: record.title,
    slug: record.slug,
    category: record.category ?? '',
    riskScore: record.risk_score ?? 0,
    riskLevel: (record.risk_level as AdminRiskLevel | null) ?? 'low',
    status: record.status as AdminPublishStatus,
    featured: record.is_featured,
    isPremium: record.is_premium,
    featuredImage: record.featured_image_url ?? undefined,
    alertsCount: record.alerts_count,
    readTimeMinutes: record.read_time_minutes,
    publishedDate: record.published_at ?? undefined,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
  };
}

/** Fields shared by create and update — `brief_type` is always fixed. */
function mapAdminBriefToWritePayload(brief: AdminBrief): BriefWritePayload {
  return {
    title: brief.title,
    slug: brief.slug || undefined,
    category: brief.category || undefined,
    risk_score: brief.riskScore,
    risk_level: brief.riskLevel,
    primary_entities: brief.primaryEntities,
    tags: brief.tags,
    time_horizon: brief.timeHorizon,
    executive_summary: brief.executiveSummary || undefined,
    why_this_matters: brief.whyThisMatters || undefined,
    key_signals: keySignalsHtmlToArray(brief.keySignals),
    risk_assessment: brief.riskAssessment || undefined,
    what_others_miss: brief.whatOthersMiss || undefined,
    implications: brief.implications || undefined,
    main_intelligence_brief: brief.mainBrief || undefined,
    analyst_notes: brief.analystNotes || undefined,
    supporting_alerts: brief.supportingAlerts.map(a => ({
      url: a.url,
      title: a.title || undefined,
    })),
    confidence_level: brief.confidenceLevel,
    brief_type: 'intelligence_brief',
    is_premium: brief.isPremium,
  };
}

export function mapAdminBriefToCreatePayload(brief: AdminBrief): CreateBriefPayload {
  return { ...mapAdminBriefToWritePayload(brief), title: brief.title };
}

export function mapAdminBriefToUpdatePayload(brief: AdminBrief): UpdateBriefPayload {
  return mapAdminBriefToWritePayload(brief);
}

export async function fetchAdminBriefsPage(
  params: FetchAdminBriefsParams,
  token: string,
): Promise<{ items: AdminBriefListItem[]; total: number; limit: number; offset: number }> {
  const res = await apiGet<AdminBriefListResponse>(buildAdminBriefsListPath(params), {
    token,
  });
  return { ...res, items: res.items.map(mapApiBriefListItemToAdminBriefListItem) };
}

export async function fetchAdminBriefDetail(
  id: string,
  token: string,
): Promise<AdminBrief> {
  const record = await apiGet<AdminBriefApiRecord>(buildAdminBriefPath(id), { token });
  return mapApiBriefToAdminBrief(record);
}

export async function createAdminBrief(
  brief: AdminBrief,
  token: string,
): Promise<AdminBrief> {
  const record = await apiPost<AdminBriefApiRecord>(
    ADMIN_BASE,
    mapAdminBriefToCreatePayload(brief),
    { token },
  );
  return mapApiBriefToAdminBrief(record);
}

export async function updateAdminBrief(
  id: string,
  brief: AdminBrief,
  token: string,
): Promise<AdminBrief> {
  const record = await apiPut<AdminBriefApiRecord>(
    buildAdminBriefPath(id),
    mapAdminBriefToUpdatePayload(brief),
    { token },
  );
  return mapApiBriefToAdminBrief(record);
}

export async function publishAdminBrief(id: string, token: string): Promise<AdminBrief> {
  const record = await apiPost<AdminBriefApiRecord>(
    `${buildAdminBriefPath(id)}/publish`,
    {},
    { token },
  );
  return mapApiBriefToAdminBrief(record);
}

export async function archiveAdminBrief(id: string, token: string): Promise<AdminBrief> {
  const record = await apiPost<AdminBriefApiRecord>(
    `${buildAdminBriefPath(id)}/archive`,
    {},
    { token },
  );
  return mapApiBriefToAdminBrief(record);
}

export async function featureAdminBrief(id: string, token: string): Promise<AdminBrief> {
  const record = await apiPost<AdminBriefApiRecord>(
    `${buildAdminBriefPath(id)}/feature`,
    {},
    { token },
  );
  return mapApiBriefToAdminBrief(record);
}

export async function unfeatureAdminBrief(id: string, token: string): Promise<AdminBrief> {
  const record = await apiPost<AdminBriefApiRecord>(
    `${buildAdminBriefPath(id)}/unfeature`,
    {},
    { token },
  );
  return mapApiBriefToAdminBrief(record);
}

export async function uploadAdminBriefImage(
  id: string,
  file: File,
  token: string,
): Promise<AdminBrief> {
  const formData = new FormData();
  formData.append('file', file);
  const record = await apiRequest<AdminBriefApiRecord>(
    `${buildAdminBriefPath(id)}/featured-image`,
    { method: 'POST', body: formData, token },
  );
  return mapApiBriefToAdminBrief(record);
}

export async function removeAdminBriefImage(
  id: string,
  token: string,
): Promise<AdminBrief> {
  const record = await apiDelete<AdminBriefApiRecord>(
    `${buildAdminBriefPath(id)}/featured-image`,
    { token },
  );
  return mapApiBriefToAdminBrief(record);
}
