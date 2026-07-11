/**
 * Canonical category list — the single source of truth for both the admin
 * create/edit form and the subscriber library's category filter, so the two
 * can never drift out of sync.
 */
export const BRIEF_CATEGORIES = [
  'Emerging Threat',
  'Fraud',
  'Phishing',
  'Cybercrime',
  'Financial Crime',
  'Regulatory',
  'Data Breach',
  'AML',
  'Sanctions',
] as const;

export type BriefCategory = (typeof BRIEF_CATEGORIES)[number];

export const BRIEF_CATEGORY_OPTIONS: ReadonlyArray<{
  value: string;
  label: string;
}> = BRIEF_CATEGORIES.map(value => ({ value, label: value }));
