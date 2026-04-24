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
};

export type AlertsListResponse = {
  alerts: AlertApiRecord[];
};
