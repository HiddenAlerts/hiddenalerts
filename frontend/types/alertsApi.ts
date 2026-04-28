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
  processed_at?: string;
  secondary_category?: string | null;
  entities?: string[];
};

export type AlertsListResponse = {
  alerts: AlertApiRecord[];
};
