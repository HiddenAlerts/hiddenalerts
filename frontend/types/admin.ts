export type AdminPublishStatus = 'draft' | 'published' | 'archived';

export type AdminRiskLevel = 'critical' | 'high' | 'medium' | 'low';

export type AdminConfidenceLevel = 'high' | 'medium' | 'low';

export type AdminTimeHorizon =
  | 'immediate'
  | 'near_term'
  | 'medium_term'
  | 'long_term';

export type AdminSupportingAlert = {
  url: string;
  title?: string;
};

export type AdminBrief = {
  id: string;
  /** Human-readable identifier assigned by the backend, e.g. "IB-2026-0042". */
  briefCode: string;
  title: string;
  /** Derived from the title; not directly editable in the form. */
  slug: string;
  category: string;
  riskScore: number;
  riskLevel: AdminRiskLevel;
  timeHorizon?: AdminTimeHorizon;
  primaryEntities: string[];
  tags: string[];
  /** Server-hosted URL once uploaded via the dedicated image endpoint. */
  featuredImage?: string;
  executiveSummary: string;
  whyThisMatters: string;
  keySignals: string;
  riskAssessment: string;
  whatOthersMiss: string;
  implications: string;
  mainBrief: string;
  /** Internal, admin-only notes — never shown to subscribers. */
  analystNotes: string;
  confidenceLevel: AdminConfidenceLevel;
  supportingAlerts: AdminSupportingAlert[];
  featured: boolean;
  /** Gates the brief behind a premium subscription tier. */
  isPremium: boolean;
  status: AdminPublishStatus;
  alertsCount: number;
  readTimeMinutes: number;
  createdAt: string;
  updatedAt: string;
  /** Set automatically once the brief is published. */
  publishedDate?: string;
};

/** Lightweight row shape for the admin briefs table (list endpoint only). */
export type AdminBriefListItem = {
  id: string;
  briefCode: string;
  title: string;
  slug: string;
  category: string;
  riskScore: number;
  riskLevel: AdminRiskLevel;
  status: AdminPublishStatus;
  featured: boolean;
  isPremium: boolean;
  featuredImage?: string;
  alertsCount: number;
  readTimeMinutes: number;
  publishedDate?: string;
  createdAt: string;
  updatedAt: string;
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
  status: 'published' | 'draft';
};

export type AdminAlertRiskExplanation = {
  scoreTotal: number;
  score100: number;
  riskLevel: string;
  riskBand: string;
  factors: {
    sourceCredibility?: number;
    financialImpact?: number;
    victimScale?: number;
    crossSource?: number;
    trendAcceleration?: number;
  };
  publicationDecision: string;
  publicationReason?: string;
  pendingReviewReason?: string;
  source: string;
  sourceCredibility: number;
};

/** Full admin alert detail from `GET /v1/alerts/{id}`. */
export type AdminAlertDetail = {
  id: string;
  title: string;
  sourceName: string;
  itemUrl: string;
  riskScore: number;
  riskLevel: string;
  riskBand: string;
  category: string;
  secondaryCategory?: string;
  date: string;
  processedAt: string;
  publishedAt?: string;
  summary: string;
  tags: string[];
  status: 'published' | 'draft';
  publishDecision: string;
  publishDecisionReason?: string;
  pendingReviewReason?: string;
  isExcluded: boolean;
  excludedReason?: string;
  isManualHold: boolean;
  publishedByRule: boolean;
  publicationStateSource?: string;
  publicationStateUpdatedAt?: string;
  publishingPolicyVersion?: string;
  reviewStatus?: string;
  eventId?: number;
  eventTitle?: string;
  financialImpactEstimate?: string;
  victimScaleRaw?: string;
  scoreBreakdown: {
    sourceCredibility?: number;
    financialImpact?: number;
    victimScale?: number;
    crossSource?: number;
    trendAcceleration?: number;
  };
  riskExplanation?: AdminAlertRiskExplanation;
};

export type AdminSubscriber = {
  id: string;
  email: string;
  joinedAt: string;
};
