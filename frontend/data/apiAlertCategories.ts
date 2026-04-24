/** Category filter values for `/api/alerts` (exact match). */
export const API_ALERT_CATEGORY_OPTIONS = [
  { value: 'all', label: 'All categories' },
  { value: 'Consumer Scam', label: 'Consumer Scam' },
  { value: 'Cryptocurrency Fraud', label: 'Cryptocurrency Fraud' },
  { value: 'Cybercrime', label: 'Cybercrime' },
  { value: 'Investment Fraud', label: 'Investment Fraud' },
  { value: 'Money Laundering', label: 'Money Laundering' },
  { value: 'Other', label: 'Other' },
] as const;
