import type { LucideIcon } from 'lucide-react';
import {
  Building2,
  CreditCard,
  FileWarning,
  Radar,
  ScanSearch,
  Shield,
  ShieldCheck,
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
  alerts: '/login',
  briefs: '/login',
  allAlerts: '/login',
  contactSales: 'mailto:hello@hiddenalerts.com',
  newsletter: 'https://hiddenalerts.beehiiv.com',
  heroSubscribe: '#top',
} as const;

export type LandingNavItem = { label: string; href: string };

export const LANDING_NAV: ReadonlyArray<LandingNavItem> = [
  { label: 'How It Works', href: LANDING_LINKS.howItWorks },
  { label: 'Alerts', href: LANDING_LINKS.alerts },
  { label: 'Intelligence Briefs', href: LANDING_LINKS.briefs },
  { label: 'Pricing', href: LANDING_LINKS.pricing },
  { label: 'FAQ', href: LANDING_LINKS.faq },
] as const;

export const HERO_CONTENT = {
  eyebrow: 'Real-Time Fraud Intelligence',
  titleLead: 'Real-Time Fraud Intelligence',
  titleEmphasis: 'Before It Hits Your Institution',
  description:
    'Early intelligence on emerging fraud threats—before they impact banks, fintechs, and compliance teams.',
  emailPlaceholder: 'Enter your email',
  emailButtonLabel: 'Get Free Weekly Intelligence Brief',
  emailFootnote: 'No spam. Unsubscribe anytime.',
  trustLine: 'Trusted by professionals in:',
  trustItems: [
    { icon: Building2, label: 'Banks' },
    { icon: Zap, label: 'Fintechs' },
    { icon: CreditCard, label: 'Payment Providers' },
    { icon: ShieldCheck, label: 'Compliance Teams' },
  ] as ReadonlyArray<{ icon: LucideIcon; label: string }>,
} as const;

export const THREAT_SIGNAL_STAT = {
  label: 'Active High-Risk Signals',
  value: '247',
  headline: 'High-Risk Threat Signals',
  caption: 'Updated in real-time from global sources',
} as const;

export type RiskLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM';

export type LiveAlert = {
  score: number;
  level: RiskLevel;
  title: string;
  category: string;
  categoryTone: 'danger' | 'info' | 'warning';
  timestamp: string;
};

export const LIVE_ALERTS: ReadonlyArray<LiveAlert> = [
  {
    score: 84,
    level: 'CRITICAL',
    title:
      'Owner of Durable Medical Equipment Company Sentenced for $59M Medicare Fraud',
    category: 'Medicare Fraud',
    categoryTone: 'danger',
    timestamp: 'May 20, 2026 · 2:11 PM UTC',
  },
  {
    score: 78,
    level: 'HIGH',
    title:
      'Operation Winter SHIELD: FBI Philadelphia on Protecting the Transportation Sector',
    category: 'Cybercrime',
    categoryTone: 'info',
    timestamp: 'May 19, 2026 · 4:50 PM UTC',
  },
  {
    score: 74,
    level: 'HIGH',
    title:
      'Former Coal Company Executive Convicted in International Bribery and Money Laundering',
    category: 'Money Laundering',
    categoryTone: 'warning',
    timestamp: 'May 18, 2026 · 6:30 AM UTC',
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
  includesTitle: 'This brief includes:',
  includes: [
    'Key Intelligence & Threat Actors',
    'Attack Methods & Tactics',
    'Risk Assessment & Impact',
    'Indicators to Watch',
    'Recommended Actions',
    'Sources & References',
  ],
  cta: { label: 'View Sample Intelligence Brief', href: LANDING_LINKS.sampleBrief },
  ctaFootnote: 'Full access included with paid plans.',
} as const;

export type HowItWorksStep = {
  step: number;
  icon: LucideIcon;
  title: string;
  description: string;
};

export const HOW_IT_WORKS = {
  title: 'How It Works',
  subtitle: 'From global signals to actionable intelligence in four simple steps.',
  steps: [
    {
      step: 1,
      icon: Radar,
      title: 'Detect',
      description:
        'We monitor global, underground, and open-source intelligence 24/7.',
    },
    {
      step: 2,
      icon: ScanSearch,
      title: 'Analyze',
      description:
        'Our analysts identify, validate, and assess the highest-risk threats.',
    },
    {
      step: 3,
      icon: FileWarning,
      title: 'Prioritize',
      description:
        'Threats are scored for risk and context so you know what matters most.',
    },
    {
      step: 4,
      icon: Shield,
      title: 'Act',
      description:
        'You receive real-time alerts and in-depth briefs to take action before losses occur.',
    },
  ] as ReadonlyArray<HowItWorksStep>,
} as const;

export const FREE_PLAN = {
  title: 'Free Weekly Intelligence Brief',
  intro: "Every Friday you'll receive:",
  features: [
    'One Featured High-Risk Alert',
    'Weekly Fraud Intelligence Summary',
    'Analyst Commentary',
    'Intelligence Brief Preview',
    'Email Delivery',
  ],
  emailPlaceholder: 'Enter your email',
  buttonLabel: 'Subscribe Free',
  actionUrl: LANDING_LINKS.newsletter,
  footnote: 'Get your first Intelligence Brief this Friday.',
} as const;

export const PROFESSIONAL_PLAN = {
  title: 'HiddenAlerts Professional',
  description:
    'Real-time fraud alerts, full intelligence briefs, and analyst-driven intelligence to help identify emerging threats before they become losses.',
  features: [
    'Real-Time Alert Feed',
    'Full Intelligence Brief Library',
    'Alert Search & Filtering',
    'Full Alert Details',
    'Full Intelligence Brief Access',
    'Email Notifications',
    'Subscriber Support',
  ],
  monthly: { amount: '$9', cadence: '/month', note: 'Billed monthly' },
  annual: {
    amount: '$79',
    cadence: '/year',
    note: 'Billed annually',
    badge: 'Save 25%',
  },
  cta: { label: 'Subscribe Now', href: LANDING_LINKS.subscribe },
  footnote: 'Secure checkout. Cancel anytime.',
} as const;


export const LANDING_FAQ = [
  {
    question: 'What is HiddenAlerts?',
    answer:
      'HiddenAlerts is a real-time fraud intelligence service that surfaces emerging threats from global sources—before they impact banks, fintechs, and financial institutions.',
  },
  {
    question: 'How is HiddenAlerts different from a news feed?',
    answer:
      'Every signal is risk-scored, validated, and enriched by our intelligence team. You get prioritized, actionable context—not raw headlines or noise.',
  },
  {
    question: 'Who is HiddenAlerts for?',
    answer:
      'Investigators, analysts, and compliance teams across banking, fintech, payments, and risk management who need early visibility into emerging fraud threats.',
  },
  {
    question: 'What do I get in the weekly newsletter?',
    answer:
      'Free subscribers receive one high-risk alert per week plus a weekly summary brief. Subscribers unlock full alerts, in-depth intelligence briefs, threat analysis, and recommended actions.',
  },
] as const;

export const FOOTER_CONTENT = {
  tagline: 'Real-time fraud intelligence. Early detection. Actionable protection.',
  newsletterTitle: 'Stay Ahead of Fraud',
  newsletterDescription:
    'Get the weekly intelligence brief and high-risk alert preview.',
  newsletterPlaceholder: 'Enter your email',
  newsletterButtonLabel: 'Subscribe Free',
  newsletterActionUrl: LANDING_LINKS.newsletter,
  securityNote: 'Built for financial institutions. Secured for intelligence.',
  productLinks: [
    { label: 'How It Works', href: LANDING_LINKS.howItWorks },
    { label: 'Alerts', href: LANDING_LINKS.alerts },
    { label: 'Intelligence Briefs', href: LANDING_LINKS.briefs },
    { label: 'Pricing', href: LANDING_LINKS.pricing },
  ],
  resourceLinks: [
    { label: 'Sample Intelligence Brief', href: LANDING_LINKS.sampleBrief },
    { label: 'FAQ', href: LANDING_LINKS.faq },
  ],
  legalLinks: [
    { label: 'Terms of Service', href: '/terms' },
    { label: 'Privacy Policy', href: '/privacy' },
    { label: 'Disclaimer', href: '/disclaimer' },
  ],
  contactLinks: [
    { label: 'Contact Us', href: 'mailto:hello@hiddenalerts.com' },
    { label: 'hello@hiddenalerts.com', href: 'mailto:hello@hiddenalerts.com' },
  ],
  socialLinks: [
    {
      href: 'https://www.linkedin.com/company/covertlytics',
      label: 'LinkedIn',
    },
    { href: 'https://x.com/covertlytics', label: 'X (Twitter)' },
    { href: 'mailto:hello@hiddenalerts.com', label: 'Email' },
  ],
  copyright: '© 2026 HiddenAlerts. All rights reserved.',
} as const;
