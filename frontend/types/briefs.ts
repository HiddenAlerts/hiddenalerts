export type BriefRiskLabel = 'Critical' | 'High' | 'Medium' | 'Low';

/**
 * Visual theme key used to render an inline gradient + icon cover for a brief.
 * Keeps card visuals consistent without bundling per-brief imagery.
 */
export type BriefCoverTheme =
  | 'emerging-threat'
  | 'financial-crime'
  | 'cyber'
  | 'national-security'
  | 'fraud'
  | 'identity'
  | 'corruption'
  | 'organized-crime';

export type SubscriberBrief = {
  id: string;
  slug: string;
  title: string;
  /** Primary category, used by the card label, category filter, and sidebar list. */
  category: string;
  /** Broader coverage tags (a brief can belong to several coverage areas). */
  coverageAreas: string[];
  /** ISO date (yyyy-mm-dd) the brief was published. */
  date: string;
  riskScore: number;
  riskLabel: BriefRiskLabel;
  coverTheme: BriefCoverTheme;
  /** Real uploaded photo, if set — falls back to the themed cover when absent. */
  featuredImage?: string;
  /** Number of supporting/verified sources cited in the brief. */
  sourceCount: number;
  /** Added or updated within the current week. */
  isNew?: boolean;
  /** Renders a "Confidential" marker on the featured/detail surfaces. */
  confidential?: boolean;
  /** Single brief surfaced in the hero "Featured Intelligence Brief" slot. */
  featured?: boolean;
  summary: string;
  href: string;
};

export type BriefRiskFilterValue = 'all' | 'critical' | 'high' | 'medium' | 'low';

export type BriefSortValue = 'newest' | 'oldest' | 'risk-high' | 'risk-low';

export type BriefFilters = {
  search: string;
  category: string;
  risk: BriefRiskFilterValue;
  sort: BriefSortValue;
};

export type BriefCountItem = {
  label: string;
  count: number;
};

export type BriefDetailRiskLevel = 'critical' | 'high' | 'medium' | 'low';

export type BriefDetailConfidenceLevel = 'high' | 'medium' | 'low';

export type BriefSupportingAlert = {
  url: string;
  title?: string;
};

/**
 * Full content for a single brief's reading view — the shape `BriefReader`
 * renders, regardless of whether the data came from the admin form or
 * subscriber mock data.
 */
export type BriefDetail = {
  id: string;
  slug: string;
  title: string;
  category: string;
  /** Fallback banner visual used when there's no `featuredImage`. */
  coverTheme: BriefCoverTheme;
  riskScore: number;
  riskLevel: BriefDetailRiskLevel;
  confidenceLevel: BriefDetailConfidenceLevel;
  primaryEntities: string[];
  tags: string[];
  featuredImage?: string;
  executiveSummary: string;
  whyThisMatters: string;
  keySignals: string;
  riskAssessment: string;
  whatOthersMiss: string;
  implications: string;
  mainBrief: string;
  supportingAlerts: BriefSupportingAlert[];
  status: 'draft' | 'published' | 'archived';
  publishedDate?: string;
};
