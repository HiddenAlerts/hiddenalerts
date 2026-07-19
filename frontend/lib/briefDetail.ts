import type { AdminBrief } from '@/types/admin';
import type {
  BriefCoverTheme,
  BriefDetail,
  BriefDetailConfidenceLevel,
  BriefDetailRiskLevel,
  BriefRiskLabel,
} from '@/types/briefs';

const CATEGORY_COVER_THEME: Record<string, BriefCoverTheme> = {
  'Emerging Threat': 'emerging-threat',
  Fraud: 'fraud',
  Phishing: 'cyber',
  Cybercrime: 'cyber',
  'Financial Crime': 'financial-crime',
  Regulatory: 'national-security',
  'Data Breach': 'cyber',
  AML: 'financial-crime',
  Sanctions: 'national-security',
};

/** Falls back to a sensible default when the category has no explicit theme. */
export function categoryToCoverTheme(category: string): BriefCoverTheme {
  return CATEGORY_COVER_THEME[category] ?? 'emerging-threat';
}

export const RISK_LEVEL_LABEL: Record<BriefDetailRiskLevel, BriefRiskLabel> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  unknown: 'Unknown',
};

export const CONFIDENCE_LEVEL_LABEL: Record<BriefDetailConfidenceLevel, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

/** Maps the admin CMS shape into the shared reader's data contract. */
export function adminBriefToDetail(brief: AdminBrief): BriefDetail {
  return {
    id: brief.id,
    slug: brief.slug,
    title: brief.title,
    category: brief.category,
    coverTheme: categoryToCoverTheme(brief.category),
    riskScore: brief.riskScore,
    riskLevel: brief.riskLevel,
    confidenceLevel: brief.confidenceLevel,
    primaryEntities: brief.primaryEntities,
    tags: brief.tags,
    featuredImage: brief.featuredImage,
    executiveSummary: brief.executiveSummary,
    whyThisMatters: brief.whyThisMatters,
    keySignals: brief.keySignals,
    riskAssessment: brief.riskAssessment,
    whatOthersMiss: brief.whatOthersMiss,
    implications: brief.implications,
    mainBrief: brief.mainBrief,
    supportingAlerts: brief.supportingAlerts,
    status: brief.status,
    publishedDate: brief.publishedDate,
  };
}
