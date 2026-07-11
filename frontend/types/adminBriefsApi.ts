

export type BriefRiskLevelApi = 'critical' | 'high' | 'medium' | 'low';

export type BriefTimeHorizonApi =
  | 'immediate'
  | 'near_term'
  | 'medium_term'
  | 'long_term';

export type BriefConfidenceLevelApi = 'high' | 'medium' | 'low';

export type BriefTypeApi =
  | 'intelligence_brief'
  | 'weekly_digest'
  | 'analyst_observation'
  | 'threat_update'
  | 'executive_summary'
  | 'premium_report';

export type BriefStatusApi = 'draft' | 'published' | 'archived';

export type SupportingAlertApi = {
  url: string;
  title?: string | null;
};


export type BriefWritePayload = {
  title?: string;
  slug?: string | null;
  category?: string | null;
  risk_score?: number | null;
  risk_level?: BriefRiskLevelApi | null;
  primary_entities?: string[] | null;
  tags?: string[] | null;
  time_horizon?: BriefTimeHorizonApi | null;
  executive_summary?: string | null;
  why_this_matters?: string | null;
  key_signals?: string[] | null;
  risk_assessment?: string | null;
  what_others_miss?: string | null;
  implications?: string | null;
  main_intelligence_brief?: string | null;
  analyst_notes?: string | null;
  supporting_alerts?: SupportingAlertApi[] | null;
  confidence_level?: BriefConfidenceLevelApi | null;
  brief_type?: BriefTypeApi | null;
  featured_order?: number | null;
  is_premium?: boolean | null;
};

export type CreateBriefPayload = BriefWritePayload & { title: string };

export type UpdateBriefPayload = BriefWritePayload;

export type AdminBriefApiRecord = {
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
  analyst_notes: string | null;
  supporting_alerts: SupportingAlertApi[] | null;
  alerts_count: number;
  confidence_level: string | null;
  status: string;
  is_featured: boolean;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  brief_type: string;
  featured_order: number | null;
  read_time_minutes: number;
  is_premium: boolean;
};

/** `IntelligenceBriefListItem` — lightweight row for the admin table. */
export type AdminBriefListItemApi = {
  id: number;
  brief_code: string;
  title: string;
  slug: string;
  category: string | null;
  risk_score: number | null;
  risk_level: string | null;
  status: string;
  is_featured: boolean;
  brief_type: string;
  is_premium: boolean;
  featured_image_url: string | null;
  alerts_count: number;
  read_time_minutes: number;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AdminBriefListResponse = {
  items: AdminBriefListItemApi[];
  total: number;
  limit: number;
  offset: number;
};
