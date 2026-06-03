export type DashboardRecentBriefIcon =
  | 'document'
  | 'phone'
  | 'package'
  | 'landmark';

export type DashboardRecentBriefRiskLabel =
  | 'Critical'
  | 'High'
  | 'Medium'
  | 'Low';

export type DashboardRecentBrief = {
  id: string;
  title: string;
  category: string;
  /** Brief type, e.g. "Executive Brief". */
  briefType: string;
  iconType: DashboardRecentBriefIcon;
  riskScore: number;
  riskLabel: DashboardRecentBriefRiskLabel;
  /** Last updated ISO timestamp displayed in the right column. */
  lastUpdatedIso: string;
  href: string;
};

export const DASHBOARD_RECENT_BRIEFS: DashboardRecentBrief[] = [
  {
    id: 'recent-brief-operation-winter-shield',
    title:
      'Operation Winter SHIELD: FBI Philadelphia on Protecting the Transportation Sector',
    category: 'Cybercrime',
    briefType: 'Executive Brief',
    iconType: 'document',
    riskScore: 84,
    riskLabel: 'Critical',
    lastUpdatedIso: '2026-05-18T16:50:00.000Z',
    href: '/dashboard',
  },
  {
    id: 'recent-brief-caller-as-a-service',
    title: 'Caller-as-a-Service Fraud Expands Across U.S.',
    category: 'Consumer Scam',
    briefType: 'Executive Brief',
    iconType: 'phone',
    riskScore: 84,
    riskLabel: 'Critical',
    lastUpdatedIso: '2026-05-18T14:11:00.000Z',
    href: '/dashboard',
  },
  {
    id: 'recent-brief-synthetic-identity-ring',
    title: 'Synthetic Identity Ring Targeting New Credit Lines',
    category: 'Financial Fraud',
    briefType: 'Executive Brief',
    iconType: 'package',
    riskScore: 78,
    riskLabel: 'High',
    lastUpdatedIso: '2026-05-16T11:40:00.000Z',
    href: '/dashboard',
  },
  {
    id: 'recent-brief-health-sector-ransomware',
    title: 'Health Sector Ransomware Campaigns Increase in Q2 2026',
    category: 'Cybercrime',
    briefType: 'Executive Brief',
    iconType: 'landmark',
    riskScore: 62,
    riskLabel: 'High',
    lastUpdatedIso: '2026-05-15T09:15:00.000Z',
    href: '/dashboard',
  },
];
