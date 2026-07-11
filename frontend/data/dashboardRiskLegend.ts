export type DashboardRiskLegendItem = {
  id: string;
  dotClass: string;
  label: string;
  description: string;
};

/** Risk score bands: Critical ≥81, High ≥71, Medium ≥61. */
export const DASHBOARD_RISK_LEGEND_ITEMS: DashboardRiskLegendItem[] = [
  {
    id: 'critical',
    dotClass: 'bg-danger',
    label: 'Critical Risk (81–100)',
    description: 'Highest-priority threat requiring immediate attention.',
  },
  {
    id: 'high',
    dotClass: 'bg-danger/70',
    label: 'High Risk (71–80)',
    description: 'Elevated threat requiring close monitoring.',
  },
  {
    id: 'medium',
    dotClass: 'bg-warning',
    label: 'Medium Risk (61–70)',
    description: 'Moderate risk; continue routine monitoring.',
  },
  {
    id: 'below_60',
    dotClass: 'bg-success',
    label: 'Below 61',
    description: 'Lower score band; limited subscriber surfacing.',
  },
];

export const DASHBOARD_RISK_LEGEND_INFO = {
  title: 'How scores are calculated',
  description:
    'Based on source reliability, signal strength, and historical patterns.',
} as const;
