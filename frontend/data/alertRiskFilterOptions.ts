/** Risk filter values for subscriber alerts list (`risk_level` query param, lowercase). */
export const ALERTS_RISK_FILTER_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
] as const;

export type AlertsRiskFilterValue =
  (typeof ALERTS_RISK_FILTER_OPTIONS)[number]['value'];
