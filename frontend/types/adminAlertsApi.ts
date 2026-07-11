/** Record from `GET /v1/alerts` (list item). */
export type AdminAlertApiRecord = {
  id: number;
  raw_item_id: number;
  title: string;
  source_name: string;
  item_url: string;
  risk_level: string;
  primary_category: string;
  signal_score_total: number;
  relevance_score: number;
  matched_keywords: string[];
  is_relevant: boolean;
  processed_at: string;
  source_published_at: string;
  is_published: boolean;
  published_at: string | null;
  risk_band: string;
  publish_decision: string;
  publish_decision_reason: string | null;
  pending_review_reason: string | null;
  is_excluded: boolean;
  excluded_reason: string | null;
  is_manual_hold: boolean;
  published_by_rule: boolean;
  publishing_policy_version: string | null;
  publication_state_source: string | null;
  publication_state_updated_at: string | null;
};

export type AdminAlertRiskExplanationFactors = {
  source_credibility?: number;
  financial_impact?: number;
  victim_scale?: number;
  cross_source?: number;
  trend_acceleration?: number;
};

/** Admin-only explanation from `GET /v1/alerts/{id}`. */
export type AdminAlertRiskExplanationApi = {
  score_total: number;
  score_100: number;
  risk_level: string;
  risk_band: string;
  factors: AdminAlertRiskExplanationFactors;
  publication_decision: string;
  publication_reason: string | null;
  pending_review_reason: string | null;
  source: string;
  source_credibility: number;
};

/** Full record from `GET /v1/alerts/{id}`. */
export type AdminAlertDetailApiRecord = AdminAlertApiRecord & {
  summary: string | null;
  secondary_category: string | null;
  entities_json: Record<string, unknown> | null;
  financial_impact_estimate: string | null;
  victim_scale_raw: string | null;
  ai_model: string | null;
  score_source_credibility: number | null;
  score_financial_impact: number | null;
  score_victim_scale: number | null;
  score_cross_source: number | null;
  score_trend_acceleration: number | null;
  event_id: number | null;
  event_title: string | null;
  review_status: string | null;
  published_by_user_id: number | null;
  risk_explanation: AdminAlertRiskExplanationApi | null;
};

export type AdminAlertReviewStatus = 'approved' | 'false_positive' | 'edited';

export type AdminAlertReviewPayload = {
  review_status: AdminAlertReviewStatus;
  edited_summary?: string;
  adjusted_risk_level?: string;
};

/** Response from `POST /v1/alerts/{id}/review`. */
export type AdminAlertReviewApiRecord = {
  id: number;
  alert_id: number;
  user_id: number;
  review_status: string;
  edited_summary: string | null;
  adjusted_risk_level: string | null;
  reviewed_at: string;
};

export type AdminAlertsListResponse = AdminAlertApiRecord[];
