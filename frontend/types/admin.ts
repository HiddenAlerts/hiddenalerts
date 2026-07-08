export type AdminPublishStatus = 'published' | 'draft';

export type AdminRiskLevel = 'critical' | 'high' | 'medium' | 'low';

export type AdminConfidenceLevel = 'high' | 'medium' | 'low';

export type AdminBrief = {
  id: string;
  title: string;
  /** Derived from the title; not directly editable in the form. */
  slug: string;
  category: string;
  riskScore: number;
  riskLevel: AdminRiskLevel;
  primaryEntities: string[];
  tags: string[];
  /** Local preview URL for the selected image (no upload backend yet). */
  featuredImage?: string;
  executiveSummary: string;
  whyThisMatters: string;
  keySignals: string;
  riskAssessment: string;
  whatOthersMiss: string;
  implications: string;
  mainBrief: string;
  confidenceLevel: AdminConfidenceLevel;
  sources: string[];
  featured: boolean;
  status: AdminPublishStatus;
  /** Internal record date; not directly editable in the form. */
  date: string;
  /** Set automatically once the brief is published. */
  publishedDate?: string;
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
