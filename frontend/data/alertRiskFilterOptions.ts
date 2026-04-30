/** Risk filter values for `/api/alerts` (`risk_level` query param, lowercase). */
export const ALERTS_RISK_FILTER_OPTIONS = [
  { value: 'all', label: 'All Alerts' },
  { value: 'high', label: 'High Risk' },
  { value: 'medium', label: 'Medium Risk' },
  { value: 'low', label: 'Low Risk' },
] as const;

export type AlertsRiskFilterValue =
  (typeof ALERTS_RISK_FILTER_OPTIONS)[number]['value'];
