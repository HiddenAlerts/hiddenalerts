export type DashboardBriefRiskTone = 'critical' | 'high' | 'medium' | 'low';

export type DashboardBriefItem = {
  id: string;
  title: string;
  category: string;
  date: string;
  riskScore: number;
  riskLabel: 'Critical' | 'High' | 'Medium' | 'Low';
  /** Visual theme key used to render an inline gradient/icon background for the card cover. */
  coverTheme:
    | 'cyber-network'
    | 'capitol'
    | 'credit-lock'
    | 'shipping-port';
  href: string;
};

/**
 * Curated mock briefs powering the dashboard "Intelligence Briefs" section.
 * Ordered by recency so the latest brief appears first.
 */
export const DASHBOARD_MOCK_BRIEFS: DashboardBriefItem[] = [
  {
    id: 'brief-foreign-remote-hiring',
    title: 'Foreign Adversaries Continue Exploiting Remote Hiring Processes',
    category: 'Cybercrime',
    date: '2026-05-18',
    riskScore: 94,
    riskLabel: 'Critical',
    coverTheme: 'cyber-network',
    href: '/briefs',
  },
  {
    id: 'brief-government-benefits-fraud',
    title: 'Government Benefits Fraud Continues Scaling in Multiple States',
    category: 'Financial Crime',
    date: '2026-05-17',
    riskScore: 89,
    riskLabel: 'Critical',
    coverTheme: 'capitol',
    href: '/briefs',
  },
  {
    id: 'brief-synthetic-identity-rings',
    title: 'Synthetic Identity Rings Expanding New Credit Lines Nationwide',
    category: 'Financial Fraud',
    date: '2026-05-16',
    riskScore: 86,
    riskLabel: 'Critical',
    coverTheme: 'credit-lock',
    href: '/briefs',
  },
  {
    id: 'brief-trade-based-money-laundering',
    title: 'Trade-Based Money Laundering Schemes Increase in Q2 2026',
    category: 'Money Laundering',
    date: '2026-05-15',
    riskScore: 82,
    riskLabel: 'High',
    coverTheme: 'shipping-port',
    href: '/briefs',
  },
];
