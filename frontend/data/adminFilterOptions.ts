import { API_ALERT_CATEGORY_OPTIONS } from './apiAlertCategories';
import { BRIEF_CATEGORY_OPTIONS } from './briefCategories';

export const ADMIN_STATUS_OPTIONS = [
  { value: 'all', label: 'All Status' },
  { value: 'published', label: 'Published' },
  { value: 'draft', label: 'Draft' },
  { value: 'archived', label: 'Archived' },
] as const;

/** Alerts list — published/draft only (`is_published` on the API). */
export const ADMIN_ALERT_STATUS_OPTIONS = [
  { value: 'all', label: 'All Status' },
  { value: 'published', label: 'Published' },
  { value: 'draft', label: 'Draft' },
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

/** Brief category options without the "all" sentinel, for create/edit forms. */
export const ADMIN_CATEGORY_FORM_OPTIONS = BRIEF_CATEGORY_OPTIONS;

/**
 * Alert taxonomy — must match the backend six categories used by the
 * subscriber alerts feed (`API_ALERT_CATEGORY_OPTIONS`).
 */
export const ADMIN_ALERT_CATEGORY_FORM_OPTIONS = API_ALERT_CATEGORY_OPTIONS.filter(
  option => option.value !== 'all',
);

export const ADMIN_RISK_LEVEL_OPTIONS = [
  { value: 'all', label: 'All Risk Levels' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
] as const;

/** Brief list/filter categories (intelligence briefs, not alerts). */
export const ADMIN_CATEGORY_OPTIONS = [
  { value: 'all', label: 'All Categories' },
  ...BRIEF_CATEGORY_OPTIONS,
];

/** Alert list/filter categories — backend taxonomy. */
export const ADMIN_ALERT_CATEGORY_OPTIONS = [
  { value: 'all', label: 'All Categories' },
  ...ADMIN_ALERT_CATEGORY_FORM_OPTIONS,
];

export type AdminStatusFilter =
  (typeof ADMIN_STATUS_OPTIONS)[number]['value'];

export type AdminRiskLevelFilter =
  (typeof ADMIN_RISK_LEVEL_OPTIONS)[number]['value'];
