import type {
  BriefRiskFilterValue,
  BriefSortValue,
  SubscriberBrief,
} from '@/types/briefs';

/**
 * Curated mock briefs powering the subscriber Intelligence Brief Library.
 * Ordered newest-first. Risk labels are derived from the score in `lib/briefs`.
 * `href` is derived from `slug` below, once the full object (with `slug`) exists.
 */
const SUBSCRIBER_MOCK_BRIEFS_SEED: Omit<SubscriberBrief, 'href'>[] = [
  {
    id: 'brief-prediction-markets',
    slug: 'prediction-markets-insider-threat',
    title:
      'Prediction Markets Are Creating New Insider Threat and National Security Risks',
    category: 'Emerging Threats',
    coverageAreas: ['Emerging Threats', 'National Security'],
    date: '2026-05-20',
    riskScore: 91,
    riskLabel: 'Critical',
    coverTheme: 'emerging-threat',
    sourceCount: 5,
    isNew: true,
    confidential: true,
    featured: true,
    summary:
      'Rapidly growing prediction markets are creating financial incentives for insiders to leak sensitive information, introducing novel national security and insider-threat exposure.',
  },
  {
    id: 'brief-industrial-scam-centers',
    slug: 'industrial-scale-scam-centers',
    title:
      'Industrial-Scale Scam Centers Continue Evolving into Transnational Criminal Enterprises',
    category: 'Organized Crime',
    coverageAreas: ['Organized Crime', 'Fraud & Financial Crime'],
    date: '2026-05-20',
    riskScore: 93,
    riskLabel: 'Critical',
    coverTheme: 'organized-crime',
    sourceCount: 5,
    isNew: true,
    summary:
      'Scam compounds are professionalizing into transnational enterprises with corporate structures, recruitment pipelines, and layered money-laundering operations.',
  },
  {
    id: 'brief-nation-state-blend',
    slug: 'nation-state-actors-blend-operations',
    title:
      'Nation-State Actors Increasingly Blend Cyberattacks, Psychological Operations and Transnational Crime',
    category: 'National Security',
    coverageAreas: ['National Security', 'Cyber Threats', 'Emerging Threats'],
    date: '2026-05-20',
    riskScore: 91,
    riskLabel: 'Critical',
    coverTheme: 'national-security',
    sourceCount: 5,
    isNew: true,
    summary:
      'State-aligned actors are fusing cyber intrusions, influence operations, and criminal proxies, blurring the line between espionage and organized crime.',
  },
  {
    id: 'brief-it-impersonation',
    slug: 'criminal-groups-impersonate-it-staff',
    title:
      'Criminal Groups Increasingly Impersonate Internal IT Staff to Bypass Security Controls',
    category: 'Cyber Threats',
    coverageAreas: ['Cyber Threats', 'Emerging Threats'],
    date: '2026-05-17',
    riskScore: 90,
    riskLabel: 'Critical',
    coverTheme: 'cyber',
    sourceCount: 4,
    summary:
      'Attackers are posing as internal IT and help-desk staff to socially engineer employees, reset credentials, and bypass MFA at scale.',
  },
  {
    id: 'brief-government-innovation',
    slug: 'fraud-corruption-government-innovation',
    title:
      'Fraud and Corruption Risks Continue Targeting High-Value Government Innovation Programs',
    category: 'Government Corruption',
    coverageAreas: ['Government Corruption', 'Fraud & Financial Crime'],
    date: '2026-05-15',
    riskScore: 89,
    riskLabel: 'Critical',
    coverTheme: 'corruption',
    sourceCount: 5,
    summary:
      'Large government innovation and grant programs are being exploited through collusion, shell vendors, and procurement fraud.',
  },
  {
    id: 'brief-enrollment-fraud',
    slug: 'organized-enrollment-fraud-networks',
    title:
      'Organized Enrollment Fraud Networks Continue Exploiting Government Benefit Programs',
    category: 'Financial Crime',
    coverageAreas: ['Fraud & Financial Crime', 'Organized Crime'],
    date: '2026-05-12',
    riskScore: 74,
    riskLabel: 'High',
    coverTheme: 'financial-crime',
    sourceCount: 4,
    summary:
      'Coordinated networks are mass-enrolling synthetic and stolen identities into benefit programs across multiple states.',
  },
  {
    id: 'brief-antifraud-infrastructure',
    slug: 'federal-anti-fraud-infrastructure',
    title:
      'Federal Authorities Expand Anti-Fraud Infrastructure as Fraud Continues Scaling',
    category: 'National Security',
    coverageAreas: ['National Security', 'Government Corruption'],
    date: '2026-05-10',
    riskScore: 87,
    riskLabel: 'Critical',
    coverTheme: 'national-security',
    sourceCount: 5,
    summary:
      'Agencies are standing up new data-sharing and detection infrastructure as fraud losses outpace legacy controls.',
  },
  {
    id: 'brief-identity-theft-networks',
    slug: 'organized-identity-theft-networks',
    title:
      'Organized Identity Theft Networks Continue Scaling Multi-State Fraud Operations',
    category: 'Financial Crime',
    coverageAreas: ['Fraud & Financial Crime', 'Organized Crime'],
    date: '2026-05-08',
    riskScore: 86,
    riskLabel: 'Critical',
    coverTheme: 'identity',
    sourceCount: 4,
    summary:
      'Identity-theft rings are industrializing document forgery and account takeover to run multi-state fraud campaigns.',
  },
  {
    id: 'brief-romance-fraud',
    slug: 'social-engineering-romance-fraud',
    title:
      'Organized Social Engineering and Romance Fraud Schemes Continue Exploiting Elderly Victims',
    category: 'Fraud',
    coverageAreas: ['Fraud & Financial Crime'],
    date: '2026-05-05',
    riskScore: 78,
    riskLabel: 'High',
    coverTheme: 'fraud',
    sourceCount: 4,
    summary:
      'Romance and trust-based fraud operations continue to target elderly victims with scripted, long-horizon social engineering.',
  },
  {
    id: 'brief-caller-as-a-service',
    slug: 'caller-as-a-service-fraud',
    title:
      'Caller-as-a-Service Fraud Expands as Organized Scam Networks Scale Corporate-Style Operations',
    category: 'Fraud',
    coverageAreas: ['Fraud & Financial Crime', 'Cyber Threats'],
    date: '2026-05-02',
    riskScore: 72,
    riskLabel: 'High',
    coverTheme: 'fraud',
    sourceCount: 4,
    summary:
      'Caller-as-a-Service platforms let fraud crews rent call-center capacity, spoofed numbers, and voice tooling on demand.',
  },
  {
    id: 'brief-legacy-crypto-fraud',
    slug: 'legacy-cryptocurrency-fraud',
    title:
      'Legacy Cryptocurrency Fraud Continues Producing Long-Term Financial Recovery Challenges',
    category: 'Financial Crime',
    coverageAreas: ['Fraud & Financial Crime'],
    date: '2026-04-28',
    riskScore: 66,
    riskLabel: 'High',
    coverTheme: 'financial-crime',
    sourceCount: 4,
    summary:
      'Victims of legacy crypto schemes continue to face long, complex financial recovery and limited restitution pathways.',
  },
];

export const SUBSCRIBER_MOCK_BRIEFS: SubscriberBrief[] = SUBSCRIBER_MOCK_BRIEFS_SEED.map(
  brief => ({ ...brief, href: `/briefs/${brief.slug}` }),
);

export const BRIEF_CATEGORY_FILTER_ALL = 'all';

export const BRIEF_RISK_FILTER_OPTIONS: ReadonlyArray<{
  value: BriefRiskFilterValue;
  label: string;
}> = [
  { value: 'all', label: 'All Levels' },
  { value: 'critical', label: 'Critical (80-100)' },
  { value: 'high', label: 'High (60-79)' },
  { value: 'medium', label: 'Medium (40-59)' },
  { value: 'low', label: 'Low (0-39)' },
];

export const BRIEF_SORT_OPTIONS: ReadonlyArray<{
  value: BriefSortValue;
  label: string;
}> = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'risk-high', label: 'Highest Risk' },
  { value: 'risk-low', label: 'Lowest Risk' },
];

export type WhySubscribersReason = {
  title: string;
  description: string;
};

/** Static value props shown in the "Why subscribers use HiddenAlerts" panel. */
export const WHY_SUBSCRIBERS_REASONS: ReadonlyArray<WhySubscribersReason> = [
  {
    title: 'Executive Summary',
    description: 'Quick understanding of the risk.',
  },
  {
    title: 'Key Signals',
    description: 'The indicators and patterns you need to know.',
  },
  {
    title: 'Risk Assessment',
    description: 'Probability, impact, and exposure analysis.',
  },
  {
    title: 'What Others Miss',
    description: 'The deeper signal behind the headlines.',
  },
  {
    title: 'Strategic Implications',
    description: 'What organizations should do to reduce risk.',
  },
  {
    title: 'Supporting Sources',
    description: 'Verified sources and citations for transparency.',
  },
];
