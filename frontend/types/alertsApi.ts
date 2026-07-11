export type AlertRiskExplanationFactorLabels = {
  source_credibility?: string;
  financial_impact?: string;
  victim_scale?: string;
  cross_source?: string;
  trend_acceleration?: string;
};

export type AlertRiskExplanationFactors = {
  source_credibility?: number;
  financial_impact?: number;
  victim_scale?: number;
  cross_source?: number;
  trend_acceleration?: number;
};

/** Curated explanation from `GET /v1/subscriber/alerts/{id}`. */
export type AlertRiskExplanation = {
  score: number;
  risk_band: string;
  risk_level: string;
  confidence: string;
  factors: AlertRiskExplanationFactors;
  factor_labels: AlertRiskExplanationFactorLabels;
  primary_exposure: string[];
  reason_for_score: string[];
};

export type AlertApiRecord = {
  id: number;
  title: string;
  summary: string;
  category: string;
  risk_level: string;
  /** Source of truth for subscriber badges (`critical` / `high` show a badge). */
  risk_band?: string;
  signal_score: number;
  source_name: string;
  source_url: string;
  published_at: string;
  /** When the original source published the material (UTC). */
  source_published_at?: string | null;
  processed_at?: string;
  secondary_category?: string | null;
  entities?: string[];
  /** When present, shown in the header “Affected” line; omitted from API until backend supplies it. */
  affected?: string | null;
  /** Search hits (`GET /search/alerts`); null for keyword-style matches. */
  matched_entity?: string | null;
};

/** Detail record includes curated `risk_explanation`. */
export type AlertDetailApiRecord = AlertApiRecord & {
  risk_explanation?: AlertRiskExplanation | null;
};

export type AlertsStatsCategoryBreakdown = {
  category: string;
  count: number;
};

/** Response from `GET /alerts/stats` (risk totals and category breakdown). */
export type AlertsStatsResponse = {
  total_alerts: number;
  critical_count?: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  category_breakdown: AlertsStatsCategoryBreakdown[];
};

export type AlertsListResponse = {
  alerts: AlertApiRecord[];
  /**
   * Total rows matching this list request (same filters as `limit`/`offset`).
   * Enables “Page X of Y” and numbered pagination. Prefer this over inferring from stats.
   */
  total?: number;
  /** Alternative field name some APIs use for the same value as `total`. */
  total_count?: number;
};

export type AlertsSearchGroup = {
  entity: string;
  group_type: string;
  alertCount: number;
  sourceCount: number;
  sources: string[];
  earliest: string;
  latest: string;
  alerts: AlertApiRecord[];
};

/** Response from `GET /search/alerts`. */
export type AlertsSearchResponse = {
  query: string;
  normalized_query: string;
  total_alerts: number;
  group_count: number;
  groups: AlertsSearchGroup[];
  alerts: AlertApiRecord[];
};
