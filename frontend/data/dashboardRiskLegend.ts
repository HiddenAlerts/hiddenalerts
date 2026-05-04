export type DashboardRiskLegendItem = {
  id: string;
  dotClass: string;
  label: string;
  description: string;
};

export const DASHBOARD_RISK_LEGEND_ITEMS: DashboardRiskLegendItem[] = [
  {
    id: 'high',
    dotClass: 'bg-danger',
    label: 'High Risk (70–100)',
    description: 'Critical threat requiring immediate attention.',
  },
  {
    id: 'medium',
    dotClass: 'bg-warning',
    label: 'Medium Risk (40–69)',
    description: 'Elevated risk requiring close monitoring.',
  },
  {
    id: 'low',
    dotClass: 'bg-success',
    label: 'Low Risk (1–39)',
    description: 'Low risk, routine monitoring.',
  },
];

export const DASHBOARD_RISK_LEGEND_INFO = {
  title: 'How scores are calculated',
  description:
    'Based on source reliability, signal strength, and historical patterns.',
} as const;
