import type { AdminAlert } from '@/types/admin';

type Seed = Pick<
  AdminAlert,
  'id' | 'title' | 'riskScore' | 'category' | 'date' | 'status'
> &
  Partial<Pick<AdminAlert, 'summary' | 'tags' | 'briefId'>>;

const SEED: Seed[] = [
  {
    id: 'alert-1',
    title: 'Scam Call Centers Surge in India and Philippines',
    riskScore: 88,
    category: 'Fraud',
    date: '2026-05-20',
    status: 'published',
    summary:
      'Intelligence indicates a surge in scam call center operations using spoofed numbers to target banking customers for OTP and credential theft.',
    briefId: 'brief-1',
    tags: ['Scam Calls', 'Telecom Fraud', 'India', 'Philippines'],
  },
  {
    id: 'alert-2',
    title: 'New Phishing Kit Targets Financial Institutions',
    riskScore: 72,
    category: 'Phishing',
    date: '2026-05-19',
    status: 'published',
  },
  {
    id: 'alert-3',
    title: 'Malware Campaign Uses Fake KYC Portals',
    riskScore: 65,
    category: 'Cybercrime',
    date: '2026-05-18',
    status: 'draft',
  },
  {
    id: 'alert-4',
    title: 'Cryptocurrency Exchange Under Regulatory Scrutiny',
    riskScore: 61,
    category: 'Regulatory',
    date: '2026-05-17',
    status: 'published',
  },
  {
    id: 'alert-5',
    title: 'Data Breach at Regional Bank Exposes PII',
    riskScore: 78,
    category: 'Data Breach',
    date: '2026-05-16',
    status: 'draft',
  },
  {
    id: 'alert-6',
    title: 'AML Reporting Gaps Detected in Cross-Border Wires',
    riskScore: 70,
    category: 'AML',
    date: '2026-05-14',
    status: 'published',
  },
  {
    id: 'alert-7',
    title: 'Suspicious Wallet Cluster Linked to Sanctioned Entity',
    riskScore: 84,
    category: 'Sanctions',
    date: '2026-05-12',
    status: 'published',
  },
  {
    id: 'alert-8',
    title: 'Fraud Ring Using Mule Accounts Detected',
    riskScore: 67,
    category: 'Fraud',
    date: '2026-05-10',
    status: 'draft',
  },
  {
    id: 'alert-9',
    title: 'New Vishing Variant Targets Bank Employees',
    riskScore: 59,
    category: 'Phishing',
    date: '2026-05-08',
    status: 'published',
  },
  {
    id: 'alert-10',
    title: 'Insider Trading Signals on Pre-IPO Tech Stocks',
    riskScore: 73,
    category: 'Financial Crime',
    date: '2026-05-06',
    status: 'draft',
  },
  {
    id: 'alert-11',
    title: 'Cybercrime Forum Selling Banking Credentials',
    riskScore: 82,
    category: 'Cybercrime',
    date: '2026-05-04',
    status: 'published',
  },
  {
    id: 'alert-12',
    title: 'Sanctions List Updated — New Entities Added',
    riskScore: 55,
    category: 'Sanctions',
    date: '2026-05-02',
    status: 'published',
  },
  {
    id: 'alert-13',
    title: 'Spike in BEC Attempts Against Logistics Firms',
    riskScore: 76,
    category: 'Fraud',
    date: '2026-04-30',
    status: 'draft',
  },
  {
    id: 'alert-14',
    title: 'Account Takeover Surge on Retail Banking Apps',
    riskScore: 80,
    category: 'Fraud',
    date: '2026-04-28',
    status: 'published',
  },
  {
    id: 'alert-15',
    title: 'Romance Scam Network Disrupted in West Africa',
    riskScore: 63,
    category: 'Fraud',
    date: '2026-04-25',
    status: 'draft',
  },
  {
    id: 'alert-16',
    title: 'Crypto ATM Network Linked to Money Laundering',
    riskScore: 79,
    category: 'AML',
    date: '2026-04-22',
    status: 'published',
  },
  {
    id: 'alert-17',
    title: 'Stolen Card Data Surge on Underground Markets',
    riskScore: 68,
    category: 'Cybercrime',
    date: '2026-04-18',
    status: 'draft',
  },
  {
    id: 'alert-18',
    title: 'New Regulatory Guidance on Stablecoin Reserves',
    riskScore: 52,
    category: 'Regulatory',
    date: '2026-04-15',
    status: 'published',
  },
];

export const ADMIN_MOCK_ALERTS: AdminAlert[] = SEED.map(s => ({
  id: s.id,
  title: s.title,
  riskScore: s.riskScore,
  category: s.category,
  date: s.date,
  status: s.status,
  summary: s.summary ?? '',
  briefId: s.briefId,
  tags: s.tags ?? [],
}));

export function findAdminAlert(id: string): AdminAlert | undefined {
  return ADMIN_MOCK_ALERTS.find(a => a.id === id);
}
