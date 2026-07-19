export type DashboardRiskLegendItem = {
  id: string;
  dotClass: string;
  label: string;
  description: string;
};

/** Subscriber-facing classifications supplied by the backend. */
export const DASHBOARD_RISK_LEGEND_ITEMS: DashboardRiskLegendItem[] = [
  {
    id: 'critical',
    dotClass: 'bg-danger',
    label: 'Critical Risk',
    description: 'Highest-priority threat requiring immediate attention.',
  },
  {
    id: 'high',
    dotClass: 'bg-danger/70',
    label: 'High Risk',
    description: 'Elevated threat requiring close monitoring.',
  },
];

export const DASHBOARD_RISK_LEGEND_INFO = {
  title: 'Backend risk classification',
  description:
    'Risk labels are supplied by HiddenAlerts scoring and review services.',
} as const;
