import { slugify } from '@/lib/utils';
import type { AdminBrief } from '@/types/admin';

import { riskScoreToLevel } from './adminFilterOptions';

type Seed = Pick<
  AdminBrief,
  'id' | 'title' | 'riskScore' | 'category' | 'date' | 'status'
> &
  Partial<
    Pick<
      AdminBrief,
      | 'slug'
      | 'primaryEntities'
      | 'tags'
      | 'executiveSummary'
      | 'keySignals'
      | 'riskAssessment'
    >
  >;

const SEED: Seed[] = [
  {
    id: 'brief-1',
    title: 'Caller-as-a-Service Fraud: The New Telecom Threat Landscape',
    riskScore: 84,
    category: 'Fraud',
    date: '2026-05-20',
    status: 'published',
    primaryEntities: ['Call Centers', 'Telecom Providers', 'Financial Institutions'],
    tags: ['Phishing', 'Social Engineering', 'Telecom Fraud'],
    executiveSummary:
      'Caller-as-a-Service (CaaS) platforms are being weaponized by fraudsters to launch large-scale scam campaigns. These operations are evading traditional telecom controls and enabling cross-border financial crime, identity theft, and social engineering at scale.',
    keySignals:
      'CaaS marketplaces resell pre-warmed numbers, voice cloning kits, and call center seats by the hour. Operators rotate carriers within minutes to avoid takedowns.',
    riskAssessment:
      'Banks and telcos with weak STIR/SHAKEN enforcement face the highest exposure. Expect a 2-3x growth in vishing-driven losses over the next two quarters.',
  },
  {
    id: 'brief-2',
    title: 'FTX Collapse — Signal Risk Patterns for Financial Institutions',
    riskScore: 91,
    category: 'Financial Crime',
    date: '2023-11-11',
    status: 'published',
  },
  {
    id: 'brief-3',
    title: 'Dark Web Credential Leakage Surge Q2 2026',
    riskScore: 77,
    category: 'Cybercrime',
    date: '2026-05-18',
    status: 'draft',
  },
  {
    id: 'brief-4',
    title: 'Synthetic Identity Networks in Southeast Asia',
    riskScore: 69,
    category: 'AML',
    date: '2026-05-15',
    status: 'draft',
  },
  {
    id: 'brief-5',
    title: 'Deepfake Social Engineering Attacks on Executives',
    riskScore: 80,
    category: 'Cybercrime',
    date: '2026-05-10',
    status: 'published',
  },
  {
    id: 'brief-6',
    title: 'Crypto Mixing Services Under New Sanctions Regime',
    riskScore: 72,
    category: 'Regulatory',
    date: '2026-05-08',
    status: 'published',
  },
  {
    id: 'brief-7',
    title: 'Sanctions Evasion via Shell Companies in Eastern Europe',
    riskScore: 88,
    category: 'AML',
    date: '2026-05-05',
    status: 'draft',
  },
  {
    id: 'brief-8',
    title: 'Phishing Campaign Targets Regional Bank Customers',
    riskScore: 64,
    category: 'Phishing',
    date: '2026-05-02',
    status: 'published',
  },
  {
    id: 'brief-9',
    title: 'Insider Trading Signals in Tech Sector IPOs',
    riskScore: 58,
    category: 'Financial Crime',
    date: '2026-04-28',
    status: 'draft',
  },
  {
    id: 'brief-10',
    title: 'Cross-Border Payment Fraud via Mule Accounts',
    riskScore: 75,
    category: 'Fraud',
    date: '2026-04-22',
    status: 'published',
  },
  {
    id: 'brief-11',
    title: 'AI-Generated Fake KYC Documents on the Rise',
    riskScore: 81,
    category: 'Fraud',
    date: '2026-04-18',
    status: 'draft',
  },
  {
    id: 'brief-12',
    title: 'Ransomware Crews Pivoting to Data Extortion Models',
    riskScore: 86,
    category: 'Cybercrime',
    date: '2026-04-12',
    status: 'published',
  },
];

export const ADMIN_MOCK_BRIEFS: AdminBrief[] = SEED.map(s => ({
  id: s.id,
  title: s.title,
  slug: s.slug ?? slugify(s.title),
  riskScore: s.riskScore,
  riskLevel: riskScoreToLevel(s.riskScore),
  category: s.category,
  date: s.date,
  primaryEntities: s.primaryEntities ?? [],
  tags: s.tags ?? [],
  executiveSummary: s.executiveSummary ?? '',
  whyThisMatters: '',
  keySignals: s.keySignals ?? '',
  riskAssessment: s.riskAssessment ?? '',
  whatOthersMiss: '',
  implications: '',
  mainBrief: '',
  confidenceLevel: 'medium',
  sources: [],
  featured: false,
  status: s.status,
}));

export function findAdminBrief(id: string): AdminBrief | undefined {
  return ADMIN_MOCK_BRIEFS.find(b => b.id === id);
}
