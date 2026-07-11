import type { BriefRiskFilterValue, BriefSortValue } from '@/types/briefs';

export const BRIEF_CATEGORY_FILTER_ALL = 'all';

/** The backend only ever returns critical/high risk briefs to subscribers. */
export const BRIEF_RISK_FILTER_OPTIONS: ReadonlyArray<{
  value: BriefRiskFilterValue;
  label: string;
}> = [
  { value: 'all', label: 'All Levels' },
  { value: 'critical', label: 'Critical (80-100)' },
  { value: 'high', label: 'High (60-79)' },
];

export const BRIEF_SORT_OPTIONS: ReadonlyArray<{
  value: BriefSortValue;
  label: string;
}> = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'risk-high', label: 'Highest Risk' },
  { value: 'risk-low', label: 'Lowest Risk' },
];

export type WhySubscribersReason = {
  title: string;
  description: string;
};

/** Static value props shown in the "Why subscribers use HiddenAlerts" panel. */
export const WHY_SUBSCRIBERS_REASONS: ReadonlyArray<WhySubscribersReason> = [
  {
    title: 'Executive Summary',
    description: 'Quick understanding of the risk.',
  },
  {
    title: 'Key Signals',
    description: 'The indicators and patterns you need to know.',
  },
  {
    title: 'Risk Assessment',
    description: 'Probability, impact, and exposure analysis.',
  },
  {
    title: 'What Others Miss',
    description: 'The deeper signal behind the headlines.',
  },
  {
    title: 'Strategic Implications',
    description: 'What organizations should do to reduce risk.',
  },
  {
    title: 'Supporting Sources',
    description: 'Verified sources and citations for transparency.',
  },
];
