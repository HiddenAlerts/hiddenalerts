import { apiGet } from '@/lib/api/client';

/** Fields used by the landing alerts card from `GET /alerts`. */
export type PublicAlertListItem = {
  id: number;
  title: string;
  category: string;
  risk_level: string;
  signal_score: number;
  source_published_at?: string | null;
  published_at?: string | null;
};

export type PublicAlertsListResponse = {
  alerts: PublicAlertListItem[];
};

export const LANDING_ALERTS_LIMIT = 5;

/**
 * Published alerts for the anonymous landing feed.
 * No auth. Uses `limit` so we only pull what the UI shows.
 */
export function fetchPublicAlerts(options?: {
  limit?: number;
  riskLevel?: 'low' | 'medium' | 'high';
}) {
  const limit = options?.limit ?? LANDING_ALERTS_LIMIT;
  const params = new URLSearchParams({
    limit: String(limit),
    offset: '0',
  });
  if (options?.riskLevel) {
    params.set('risk_level', options.riskLevel);
  }
  return apiGet<PublicAlertsListResponse>(`/alerts?${params.toString()}`);
}
