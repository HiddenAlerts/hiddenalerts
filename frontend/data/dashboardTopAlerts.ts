export type DashboardTopAlertRiskTone = 'high' | 'medium' | 'low';

export type DashboardTopAlertTagSegment = {
  text: string;
  /** Muted body vs info (blue-ish) accent */
  tone?: 'default' | 'info';
  /** Small red status dot before this segment */
  dot?: boolean;
};

export type DashboardTopAlertIconVariant = 'landmark' | 'wallet' | 'user-lock';

export type DashboardTopAlertItem = {
  id: string;
  rank: number;
  score: number;
  title: string;
  tags: DashboardTopAlertTagSegment[];
  description: string;
  occurredAt: string;
  iconVariant: DashboardTopAlertIconVariant;
};

/** Dummy featured alerts until API wiring. */
export const DASHBOARD_TOP_ALERTS: DashboardTopAlertItem[] = [
  {
    id: 'top-1',
    rank: 1,
    score: 92,
    title: 'New OFAC Sanctions: Russian Entity',
    tags: [
      { text: 'Sanctions', tone: 'info' },
      { text: 'OFAC', tone: 'info' },
    ],
    description:
      'OFAC added a Russian entity to the SDN list for supporting military industrial operations.',
    occurredAt: '2026-05-28T09:15:00.000Z',
    iconVariant: 'landmark',
  },
  {
    id: 'top-2',
    rank: 2,
    score: 87,
    title: 'Binance Wallet Exposure Detected',
    tags: [
      { text: 'Crypto / Wallet Risk', tone: 'default', dot: true },
      { text: 'On-chain Analysis', tone: 'default' },
    ],
    description:
      'Several high-risk addresses linked to previously flagged entity on Binance Smart Chain.',
    occurredAt: '2026-05-28T08:40:00.000Z',
    iconVariant: 'wallet',
  },
  {
    id: 'top-3',
    rank: 3,
    score: 82,
    title: 'Unusual Login Activity',
    tags: [
      { text: 'Account Takeover', tone: 'default', dot: true },
      { text: 'Internal Detection', tone: 'default' },
    ],
    description:
      'Multiple failed login attempts detected from new device across multiple regions.',
    occurredAt: '2026-05-28T07:55:00.000Z',
    iconVariant: 'user-lock',
  },
];
