import { BRIEF_CATEGORY_OPTIONS } from './briefCategories';

export const ADMIN_STATUS_OPTIONS = [
  { value: 'all', label: 'All Status' },
  { value: 'published', label: 'Published' },
  { value: 'draft', label: 'Draft' },
  { value: 'archived', label: 'Archived' },
] as const;

/** Form-only options (no "all" sentinel). */
export const ADMIN_RISK_LEVEL_FORM_OPTIONS = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
] as const;

export const ADMIN_CONFIDENCE_LEVEL_OPTIONS = [
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
] as const;

export const ADMIN_TIME_HORIZON_OPTIONS = [
  { value: 'immediate', label: 'Immediate' },
  { value: 'near_term', label: 'Near-term' },
  { value: 'medium_term', label: 'Medium-term' },
  { value: 'long_term', label: 'Long-term' },
] as const;

/** Category options without the "all" sentinel, for create/edit forms. */
export const ADMIN_CATEGORY_FORM_OPTIONS = BRIEF_CATEGORY_OPTIONS;

export const ADMIN_RISK_LEVEL_OPTIONS = [
  { value: 'all', label: 'All Risk Levels' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
] as const;

export const ADMIN_CATEGORY_OPTIONS = [
  { value: 'all', label: 'All Categories' },
  ...BRIEF_CATEGORY_OPTIONS,
];

export type AdminStatusFilter =
  (typeof ADMIN_STATUS_OPTIONS)[number]['value'];

export type AdminRiskLevelFilter =
  (typeof ADMIN_RISK_LEVEL_OPTIONS)[number]['value'];

/**
 * Maps a numeric risk score to a coarse risk level used by the risk filter.
 */
export function riskScoreToLevel(
  score: number,
): 'critical' | 'high' | 'medium' | 'low' {
  if (score >= 90) return 'critical';
  if (score >= 80) return 'high';
  if (score >= 60) return 'medium';
  return 'low';
}
