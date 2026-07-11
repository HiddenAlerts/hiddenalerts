export type SupportingAlertApi = {
  url: string;
  title?: string | null;
};

/** Card-level shape returned by the paginated list endpoint. */
export type SubscriberBriefListItemApi = {
  id: number;
  brief_code: string;
  title: string;
  slug: string;
  category: string | null;
  risk_score: number | null;
  risk_level: string | null;
  featured_image_url: string | null;
  time_horizon: string | null;
  executive_summary: string | null;
  tags: string[] | null;
  primary_entities: string[] | null;
  alerts_count: number;
  read_time_minutes: number;
  is_featured: boolean;
  published_at: string | null;
};

export type SubscriberBriefListResponse = {
  items: SubscriberBriefListItemApi[];
  total: number;
  limit: number;
  offset: number;
};

/** Full content shape returned by `/featured` and `/{slug}`. */
export type SubscriberBriefDetailApi = {
  id: number;
  brief_code: string;
  title: string;
  slug: string;
  category: string | null;
  risk_score: number | null;
  risk_level: string | null;
  primary_entities: string[] | null;
  tags: string[] | null;
  featured_image_url: string | null;
  time_horizon: string | null;
  executive_summary: string | null;
  why_this_matters: string | null;
  key_signals: string[] | null;
  risk_assessment: string | null;
  what_others_miss: string | null;
  implications: string | null;
  main_intelligence_brief: string | null;
  supporting_alerts: SupportingAlertApi[] | null;
  alerts_count: number;
  confidence_level: string | null;
  read_time_minutes: number;
  is_featured: boolean;
  published_at: string | null;
};
