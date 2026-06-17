export type AdminPublishStatus = 'published' | 'draft';

export type AdminRiskLevel = 'high' | 'medium' | 'low';

export type AdminTimeHorizon = 'short-term' | 'medium-term' | 'long-term';

export type AdminBrief = {
  id: string;
  title: string;
  slug: string;
  riskScore: number;
  riskLevel: AdminRiskLevel;
  category: string;
  date: string;
  timeHorizon: AdminTimeHorizon;
  primaryEntities: string[];
  tags: string[];
  executiveSummary: string;
  keyIntelligence: string;
  riskAssessment: string;
  status: AdminPublishStatus;
};

export type AdminAlert = {
  id: string;
  title: string;
  riskScore: number;
  category: string;
  date: string;
  summary: string;
  /** ID of a related brief, if any. */
  briefId?: string;
  tags: string[];
  status: AdminPublishStatus;
};

export type AdminSubscriber = {
  id: string;
  email: string;
  joinedAt: string;
};
