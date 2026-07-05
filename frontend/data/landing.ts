import type { LucideIcon } from 'lucide-react';
import {
  AlertTriangle,
  Banknote,
  BellRing,
  Building2,
  Clock,
  CreditCard,
  Layers,
  ListChecks,
  Radar,
  ScanSearch,
  ShieldCheck,
  TerminalSquare,
  Users,
  Zap,
} from 'lucide-react';

/** Routes / anchors used across the landing page. Centralised so links stay in sync. */
export const LANDING_LINKS = {
  signup: '/signup',
  login: '/login',
  subscribe: '/subscribe',
  sampleBrief: '#sample-brief',
  pricing: '#pricing',
  howItWorks: '#how-it-works',
  faq: '#faq',
  allAlerts: '/login',
  contactSales: 'mailto:contact@covertlytics.com',
  newsletter: 'https://hiddenalerts.beehiiv.com',
} as const;

export type LandingNavItem = { label: string; href: string };

export const LANDING_NAV: ReadonlyArray<LandingNavItem> = [
  { label: 'How It Works', href: LANDING_LINKS.howItWorks },
  { label: 'Sample Brief', href: LANDING_LINKS.sampleBrief },
  { label: 'Pricing', href: LANDING_LINKS.pricing },
  { label: 'FAQ', href: LANDING_LINKS.faq },
  { label: 'Login', href: LANDING_LINKS.login },
] as const;

export const HERO_CONTENT = {
  eyebrow: 'Real-Time Fraud Intelligence',
  titleLead: 'Real-Time Fraud Intelligence',
  titleEmphasis: 'Before It Hits Your Institution',
  description:
    'Daily intelligence on emerging fraud threats—before they impact banks, fintechs, and financial institutions.',
  secondaryDescription:
    'Fraud campaigns like these have led to multi-million dollar losses across financial institutions.',
  primaryCta: { label: 'Start Monitoring Threats Now', href: LANDING_LINKS.signup },
  secondaryCta: { label: 'View Sample Brief', href: LANDING_LINKS.sampleBrief },
  ctaFootnote: 'View Sample Brief opens a preview of our latest intelligence brief.',
  tiers: [
    {
      label: 'Free',
      title: 'Weekly alert + summary',
      description: '1 high-risk alert + weekly intelligence brief',
    },
    {
      label: 'Paid',
      title: 'Full alerts + intelligence briefs',
      description: 'Full threat details, analysis & recommended actions',
    },
  ],
  trustLine: 'Used by professionals in banking, fintech, and compliance.',
} as const;

export const THREAT_SIGNAL_STAT = {
  label: 'Active high-risk threat signals',
  value: '247',
  headline: 'High-Risk Threat Signals',
  detected: 'Detected (Last 24h)',
  caption: 'Updated in real-time from global threat sources',
} as const;

export type FeatureHighlight = {
  icon: LucideIcon;
  title: string;
  description: string;
};

export const FEATURE_HIGHLIGHTS: ReadonlyArray<FeatureHighlight> = [
  {
    icon: Radar,
    title: 'Curated Daily Intelligence',
    description:
      'High-risk fraud signals filtered from noise—focused on what matters now.',
  },
  {
    icon: ShieldCheck,
    title: 'Expert Analysis',
    description:
      'Each alert enriched with context, patterns, and threat significance from our intelligence team.',
  },
  {
    icon: Zap,
    title: 'Early Signal Detection',
    description:
      'Identify emerging fraud campaigns before they go mainstream—so you can act first.',
  },
] as const;

export type ProblemPoint = {
  icon: LucideIcon;
  title: string;
  description: string;
};

export const PROBLEM_SECTION = {
  title: "You're seeing fraud too late",
  points: [
    {
      icon: AlertTriangle,
      title: 'Fraud evolves faster than detection',
      description:
        "Fraud campaigns adapt quickly—traditional systems can't keep up.",
    },
    {
      icon: Clock,
      title: 'Public reports come after the damage',
      description: 'By the time threats are public, the impact is already felt.',
    },
    {
      icon: Layers,
      title: 'Critical signals are buried across fragmented sources',
      description: 'Too much noise, not enough clarity on what truly matters.',
    },
  ] as ReadonlyArray<ProblemPoint>,
  resultLabel: 'The result:',
  resultText: 'Delayed response, financial exposure, and regulatory risk.',
} as const;

export type RiskLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM';

export type LiveAlert = {
  rank: number;
  score: number;
  level: RiskLevel;
  title: string;
  category: string;
  categoryTone: 'danger' | 'info' | 'warning';
  timestamp: string;
  icon: LucideIcon;
};

export const LIVE_ALERTS: ReadonlyArray<LiveAlert> = [
  {
    rank: 1,
    score: 84,
    level: 'CRITICAL',
    title:
      'Owner of Durable Medical Equipment Company Sentenced for $59M Medicare Fraud',
    category: 'Medicare Fraud',
    categoryTone: 'danger',
    timestamp: 'May 20, 2026 · 2:11 PM UTC',
    icon: CreditCard,
  },
  {
    rank: 2,
    score: 78,
    level: 'HIGH',
    title:
      'Operation Winter SHIELD: FBI Philadelphia on Protecting the Transportation Sector',
    category: 'Cybercrime',
    categoryTone: 'info',
    timestamp: 'May 19, 2026 · 4:50 PM UTC',
    icon: TerminalSquare,
  },
  {
    rank: 3,
    score: 74,
    level: 'HIGH',
    title:
      'Former Coal Company Executive Convicted in International Bribery and Money Laundering',
    category: 'Money Laundering',
    categoryTone: 'warning',
    timestamp: 'May 18, 2026 · 6:30 AM UTC',
    icon: Banknote,
  },
] as const;

export const LIVE_ALERTS_PANEL = {
  title: 'Live High-Risk Alerts',
  viewAllLabel: 'View all alerts',
  viewAllHref: LANDING_LINKS.allAlerts,
  footnote: 'Real threats. Verified sources. Updated continuously.',
} as const;

export const INTELLIGENCE_BRIEF_PREVIEW = {
  eyebrow: 'Intelligence Brief Preview',
  score: 84,
  title:
    'Operation Winter SHIELD: FBI Philadelphia on Protecting the Transportation Sector',
  date: 'March 3, 2026 · 4:50 PM UTC',
  summary:
    'Operation Winter SHIELD, led by the FBI Philadelphia, focuses on protecting the transportation and logistics sector from cyber threats, particularly phishing attacks. The initiative aims to raise awareness, provide resources, and enhance cybersecurity measures to safeguard critical infrastructure.',
  includesTitle: 'Brief includes:',
  includes: [
    'Key Intelligence & Threat Actors',
    'Attack Methods & Tactics',
    'Risk Assessment & Impact',
    'Indicators to Watch',
    'Recommended Actions',
    'Sources & References',
  ],
  note: 'Free users see summaries. Subscribers get full intelligence, threat analysis, and recommended actions.',
  cta: { label: 'Unlock Full Intelligence Brief', href: LANDING_LINKS.subscribe },
  ctaFootnote: 'This will take you to our subscription plans.',
} as const;

export type HowItWorksStep = {
  step: number;
  icon: LucideIcon;
  title: string;
  description: string;
};

export const HOW_IT_WORKS = {
  title: 'How it works',
  subtitle: 'From global signals to actionable intelligence in four steps.',
  steps: [
    {
      step: 1,
      icon: Radar,
      title: 'Signals Detected',
      description:
        'We monitor global sources, underground forums, dark web, and open-source intelligence 24/7.',
    },
    {
      step: 2,
      icon: ScanSearch,
      title: 'Threats Analyzed',
      description:
        'Our analysts and AI identify, validate, and prioritize the highest risk threats.',
    },
    {
      step: 3,
      icon: ListChecks,
      title: 'Intelligence Delivered',
      description:
        'You receive real-time alerts and in-depth briefs with actionable context.',
    },
    {
      step: 4,
      icon: ShieldCheck,
      title: 'Action Taken',
      description:
        'Stay ahead of threats, protect your institution, and reduce exposure before it becomes loss.',
    },
  ] as ReadonlyArray<HowItWorksStep>,
} as const;

export const NEWSLETTER_CTA = {
  title: 'Get 1 high-risk alert + weekly intelligence brief (free)',
  description:
    'Join thousands of professionals getting early threat intelligence.',
  placeholder: 'Enter your work email',
  buttonLabel: 'Subscribe Free',
  actionUrl: LANDING_LINKS.newsletter,
  perks: [
    '1 high-risk alert per week',
    'Weekly summary brief',
    'Expert-curated intelligence',
    'Risk-scored, actionable context',
  ],
} as const;

export type BillingCycle = 'monthly' | 'annual';

export type PricingPlan = {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon;
  highlighted?: boolean;
  badge?: string;
  prices: Record<
    BillingCycle,
    { amount: string; cadence?: string; note?: string }
  >;
  cta: Record<BillingCycle, { label: string; href: string }>;
  features: string[];
};

export const PRICING_SECTION = {
  title: 'Choose the intelligence edge your institution needs',
  introNote: 'Introductory Pricing — Limited Time',
  urgencyNote: 'Intro pricing ends soon. Lock in your rate today.',
  toggle: {
    monthly: 'Pay Monthly',
    annual: 'Pay Annually (Save 25%)',
  },
  plans: [
    {
      id: 'professional',
      name: 'Professional',
      description: 'Essential intelligence for individuals and small teams.',
      icon: Users,
      prices: {
        monthly: { amount: '$9.00', cadence: '/month', note: 'Introductory pricing' },
        annual: {
          amount: '$81.00',
          cadence: '/year',
          note: 'Introductory pricing (billed annually)',
        },
      },
      cta: {
        monthly: { label: 'Subscribe Monthly', href: LANDING_LINKS.subscribe },
        annual: { label: 'Subscribe Annually', href: LANDING_LINKS.subscribe },
      },
      features: [
        'Real-time high-risk alerts',
        'Weekly summary brief',
        'Email notifications',
        'Standard support',
      ],
    },
    {
      id: 'team',
      name: 'Team',
      description: 'Advanced intelligence for growing teams and departments.',
      icon: Building2,
      highlighted: true,
      badge: 'Most Popular',
      prices: {
        monthly: {
          amount: '$8.25',
          cadence: '/month',
          note: 'Introductory pricing (billed annually)',
        },
        annual: {
          amount: '$79.00',
          cadence: '/year',
          note: 'Introductory pricing (billed annually)',
        },
      },
      cta: {
        monthly: { label: 'Subscribe Annually', href: LANDING_LINKS.subscribe },
        annual: { label: 'Subscribe Annually', href: LANDING_LINKS.subscribe },
      },
      features: [
        'Everything in Professional',
        'API access',
        'Team access (up to 5 users)',
        'Priority support',
      ],
    },
    {
      id: 'enterprise',
      name: 'Enterprise',
      description: 'Custom intelligence solutions for large organizations.',
      icon: BellRing,
      prices: {
        monthly: { amount: 'Custom', note: 'Contact us for pricing' },
        annual: { amount: 'Custom', note: 'Contact us for pricing' },
      },
      cta: {
        monthly: { label: 'Contact Sales', href: LANDING_LINKS.contactSales },
        annual: { label: 'Contact Sales', href: LANDING_LINKS.contactSales },
      },
      features: [
        'Everything in Team',
        'Unlimited users',
        'Custom integrations',
        'Dedicated account manager',
      ],
    },
  ] as ReadonlyArray<PricingPlan>,
} as const;

export type TrustItem = { icon: LucideIcon; label: string };

export const TRUST_BAR = {
  title:
    'Trusted by professionals across financial services, compliance, and risk management.',
  items: [
    { icon: Building2, label: 'Banks' },
    { icon: Zap, label: 'Fintechs' },
    { icon: CreditCard, label: 'Payment Providers' },
    { icon: Users, label: 'Compliance Teams' },
  ] as ReadonlyArray<TrustItem>,
} as const;

export const LANDING_FAQ = [
  {
    question: 'What is HiddenAlerts?',
    answer:
      'HiddenAlerts is a real-time fraud intelligence service that surfaces emerging threats from global sources—before they impact banks, fintechs, and financial institutions.',
  },
  {
    question: 'How is this different from a news feed?',
    answer:
      'Every signal is risk-scored, validated, and enriched by our intelligence team. You get prioritized, actionable context—not raw headlines or noise.',
  },
  {
    question: 'What do free users get?',
    answer:
      'Free users receive one high-risk alert per week plus a weekly summary brief. Subscribers unlock full alerts, in-depth intelligence briefs, threat analysis, and recommended actions.',
  },
  {
    question: 'Who is HiddenAlerts built for?',
    answer:
      'Investigators, analysts, and compliance teams across banking, fintech, payments, and risk management who need early visibility into emerging fraud threats.',
  },
] as const;
