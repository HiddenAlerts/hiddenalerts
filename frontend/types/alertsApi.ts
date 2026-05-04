export type AlertApiRecord = {
  id: number;
  title: string;
  summary: string;
  category: string;
  risk_level: string;
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
};

export type AlertsStatsCategoryBreakdown = {
  category: string;
  count: number;
};

/** Response from `GET /alerts/stats` (risk totals and category breakdown). */
export type AlertsStatsResponse = {
  total_alerts: number;
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
