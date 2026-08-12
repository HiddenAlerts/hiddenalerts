import { apiGet } from '@/lib/api/client';

/**
 * Marketing teaser from `GET /alerts` (at most 3 Critical/High alerts).
 * Current public payload — no id, signal_score, risk_level, or source fields.
 */
export type PublicAlertListItem = {
  title: string;
  risk_band: string;
  category: string;
  /** HiddenAlerts publication time (sort key). */
  published_at: string;
  summary?: string | null;
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
