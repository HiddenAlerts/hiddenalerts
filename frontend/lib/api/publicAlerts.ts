import { apiGet } from '@/lib/api/client';

/**
 * Marketing teaser from `GET /alerts` (at most 3 Critical/High alerts).
 * Score, id, and legacy risk_level were removed from the public payload.
 */
export type PublicAlertListItem = {
  title: string;
  risk_band?: string | null;
  category: string;
  published_at?: string | null;
  summary?: string | null;
  /** Legacy fields — ignored when absent. */
  risk_level?: string | null;
  source_published_at?: string | null;
  id?: number;
  signal_score?: number;
};

export type PublicAlertsListResponse = {
  alerts: PublicAlertListItem[];
};

/** Approved mockup shows three most recent high-risk alerts. */
export const LANDING_ALERTS_LIMIT = 3;

/**
 * Published teaser alerts for the anonymous landing feed.
 * No auth. Uses `limit` so we only pull what the UI shows (API caps at 3).
 */
export function fetchPublicAlerts(options?: { limit?: number }) {
  const limit = options?.limit ?? LANDING_ALERTS_LIMIT;
  const params = new URLSearchParams({
    limit: String(limit),
  });
  return apiGet<PublicAlertsListResponse>(`/alerts?${params.toString()}`);
}
