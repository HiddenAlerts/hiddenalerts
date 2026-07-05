export type DashboardTopAlertWeeklyIcon =
  | 'phone'
  | 'package'
  | 'landmark'
  | 'shield';

export type DashboardTopAlertWeeklyRiskTone = 'critical' | 'high' | 'medium';

export type DashboardTopAlertWeeklyItem = {
  id: string;
  title: string;
  /** Inline tag segments displayed in info-blue, separated by bullets. */
  tags: string[];
  /** Short headline subtitle shown under the tags. */
  headline: string;
  description: string;
  riskScore: number;
  riskTone: DashboardTopAlertWeeklyRiskTone;
  /** Risk label paired with the score (e.g. "Critical Risk"). */
  riskLabel: string;
  /** Score range pill (e.g. "80-100"). */
  riskRange: string;
  iconType: DashboardTopAlertWeeklyIcon;
  isNew: boolean;
  occurredAtIso: string;
  href: string;
};

export const DASHBOARD_TOP_ALERTS_THIS_WEEK: DashboardTopAlertWeeklyItem[] = [
  {
    id: 'top-week-caller-as-a-service',
    title: 'Caller-as-a-Service Fraud Expands Across U.S.',
    tags: ['Consumer Scam', 'FBI in the News RSS'],
    headline: 'Targeting regional banks via phishing kits',
    description:
      'Fraudsters are using legitimate VoIP infrastructure to impersonate government agencies and financial institutions. Campaigns are surging across multiple states.',
    riskScore: 84,
    riskTone: 'critical',
    riskLabel: 'Critical Risk',
    riskRange: '80-100',
    iconType: 'phone',
    isNew: true,
    occurredAtIso: '2026-05-18T14:11:00.000Z',
    href: '/alerts',
  },
  {
    id: 'top-week-operation-winter-shield',
    title:
      'Operation Winter SHIELD: FBI Philadelphia on Protecting the Transportation Sector',
    tags: ['Cybercrime', 'FBI in the News RSS'],
    headline: 'Coordinated push to harden logistics and trucking networks',
    description:
      'Operation Winter SHIELD focuses on protecting the transportation and logistics sector from cyber threats, particularly phishing attacks and credential theft.',
    riskScore: 78,
    riskTone: 'high',
    riskLabel: 'High Risk',
    riskRange: '60-79',
    iconType: 'package',
    isNew: true,
    occurredAtIso: '2026-05-18T16:50:00.000Z',
    href: '/alerts',
  },
  {
    id: 'top-week-former-coal-exec',
    title:
      'Former Coal Company Executive Convicted in International Money Laundering Scheme',
    tags: ['Financial Crime', 'DOJ Press Releases'],
    headline: 'Cross-border laundering through shell entities and proxies',
    description:
      'A former executive funneled illicit proceeds through layered shell companies in Eastern Europe to obscure the origin of more than $40 million in payments.',
    riskScore: 71,
    riskTone: 'high',
    riskLabel: 'High Risk',
    riskRange: '60-79',
    iconType: 'landmark',
    isNew: false,
    occurredAtIso: '2026-05-17T18:32:00.000Z',
    href: '/alerts',
  },
];
