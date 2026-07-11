/** Record from `GET /v1/alerts`. */
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

export type AdminAlertsListResponse = AdminAlertApiRecord[];
