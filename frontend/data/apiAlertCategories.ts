export const API_ALERT_CATEGORY_OPTIONS = [
  { value: 'all', label: 'All Type' },
  { value: 'Cybercrime', label: 'Cybercrime' },
  { value: 'Money Laundering', label: 'Money Laundering' },
  { value: 'Consumer Scam', label: 'Consumer Scam' },
  { value: 'Investment Fraud', label: 'Investment Fraud' },
  { value: 'Cryptocurrency Fraud', label: 'Cryptocurrency Fraud' },
  { value: 'Other', label: 'Other' },
] as const;

export type AlertsCategoryFilterValue =
  (typeof API_ALERT_CATEGORY_OPTIONS)[number]['value'];
