import type { LucideIcon } from 'lucide-react';
import {
  Building2,
  Clock,
  FileWarning,
  Radar,
  ScanSearch,
  Shield,
  ShieldCheck,
  UserRound,
} from 'lucide-react';

import {
  MAILERLITE_FOOTER_ANCHOR,
  MAILERLITE_PRICING_ANCHOR,
} from '@/data/mailerlite';
import { ACCOUNT_TAKEOVER_ECONOMY_BRIEF } from '@/data/sampleBriefs/accountTakeoverEconomy';
import { SAMPLE_INTELLIGENCE_BRIEFS } from '@/data/sampleIntelligenceBriefs';

/** Routes / anchors used across the landing page. Centralised so links stay in sync. */
export const LANDING_LINKS = {
  signup: '/signup',
  login: '/login',
  subscribe: '/subscribe',
  /** External Elementor sample brief (client-maintained). */
  sampleBrief: 'https://hiddenalerts.ai/account-takeover-economy',
  pricing: '#pricing',
  howItWorks: '#how-it-works',
  faq: '#faq',
  /** In-page marketing preview — never subscriber dashboard. */
  alerts: '#alerts',
  briefs: '#intelligence-brief',
  contactSales: 'mailto:hello@hiddenalerts.com',
  /** Free newsletter — MailerLite on pricing + footer (not hero). */
  newsletter: MAILERLITE_PRICING_ANCHOR,
  heroSubscribe: MAILERLITE_PRICING_ANCHOR,
  footerNewsletter: MAILERLITE_FOOTER_ANCHOR,
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
  eyebrow: 'Early Fraud Intelligence',
  titleLead: 'Early Fraud Intelligence',
  titleEmphasis: 'Before It Impacts Your Institution',
  description:
    'Actionable intelligence on emerging fraud threats from government, regulatory, cyber, and financial crime sources—validated by experts so you can act before losses occur.',
  ctaLabel: 'Join Free Intelligence Updates',
  emailFootnote: 'No spam. Unsubscribe anytime.',
} as const;

export const THREAT_SIGNAL_STAT = {
  label: 'Active High-Risk Signals',
  value: '247',
  headline: 'High-Risk Threat Signals',
  caption: 'Updated in real-time from global sources',
} as const;

export type ValueProp = {
  icon: LucideIcon;
  title: string;
  description: string;
};

export const VALUE_PROPS: ReadonlyArray<ValueProp> = [
  {
    icon: Building2,
    title: 'Government & Regulatory Sources',
    description: 'Trusted intelligence from 10+ leading sources.',
  },
  {
    icon: UserRound,
    title: '30+ Years Financial Crime Experience',
    description: 'Decades of banking and investigative expertise.',
  },
  {
    icon: Clock,
    title: 'Continuous Monitoring',
    description: 'Global coverage, updated around the clock.',
  },
  {
    icon: ShieldCheck,
    title: 'Human + AI Validation',
    description: 'Every alert analyzed and validated by experts.',
  },
] as const;

export type RiskLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM';

export type LiveAlert = {
  score: number;
  level: RiskLevel;
  title: string;
  category: string;
  categoryTone: 'danger' | 'info' | 'warning';
  timestamp: string;
};

/** Marketing alerts card — three sample Intelligence Briefs (preview only). */
export const LIVE_ALERTS: ReadonlyArray<LiveAlert> = [
  {
    score: SAMPLE_INTELLIGENCE_BRIEFS[0].riskScore,
    level: 'CRITICAL',
    title: SAMPLE_INTELLIGENCE_BRIEFS[0].title,
    category: SAMPLE_INTELLIGENCE_BRIEFS[0].category,
    categoryTone: 'danger',
    timestamp: 'June 10, 2026 · 12:55 PM UTC',
  },
  {
    score: SAMPLE_INTELLIGENCE_BRIEFS[1].riskScore,
    level: 'CRITICAL',
    title: SAMPLE_INTELLIGENCE_BRIEFS[1].title,
    category: SAMPLE_INTELLIGENCE_BRIEFS[1].category,
    categoryTone: 'info',
    timestamp: 'June 6, 2026',
  },
  {
    score: SAMPLE_INTELLIGENCE_BRIEFS[2].riskScore,
    level: 'CRITICAL',
    title: SAMPLE_INTELLIGENCE_BRIEFS[2].title,
    category: SAMPLE_INTELLIGENCE_BRIEFS[2].category,
    categoryTone: 'warning',
    timestamp: 'June 5, 2026',
  },
] as const;

export const LIVE_ALERTS_PANEL = {
  title: 'Latest High-Risk Alerts',
  badge: 'Subscriber Preview',
  footnote:
    'Additional real-time alerts are available to subscribers.',
} as const;

/**
 * Landing Intelligence Brief Preview card (Ken mockup).
 * Copy/metadata come from the published Account Takeover brief.
 * Full brief body is not rendered here — CTA opens the published page.
 */
export const INTELLIGENCE_BRIEF_PREVIEW = {
  eyebrow: 'Intelligence Brief Preview',
  coverSrc: ACCOUNT_TAKEOVER_ECONOMY_BRIEF.thumbnailSrc,
  coverAlt:
    'Cover art for The Account Takeover Economy intelligence brief',
  score: ACCOUNT_TAKEOVER_ECONOMY_BRIEF.riskScore,
  riskLevel: ACCOUNT_TAKEOVER_ECONOMY_BRIEF.riskLevel,
  categories: ACCOUNT_TAKEOVER_ECONOMY_BRIEF.categoriesLabel,
  title: ACCOUNT_TAKEOVER_ECONOMY_BRIEF.title,
  summary: ACCOUNT_TAKEOVER_ECONOMY_BRIEF.landingPreviewSummary,
  highlightLead: 'Learn how',
  highlightBrand: 'HiddenAlerts',
  highlightTrail:
    'identifies these emerging fraud signals before they become major losses.',
  publishedLabel: ACCOUNT_TAKEOVER_ECONOMY_BRIEF.publishedLabel,
  sourceCount: String(ACCOUNT_TAKEOVER_ECONOMY_BRIEF.sourceCount),
  timeHorizon: ACCOUNT_TAKEOVER_ECONOMY_BRIEF.timeHorizon,
  cta: {
    label: 'View Full Intelligence Brief',
    href: LANDING_LINKS.sampleBrief,
  },
  footer: 'Actionable intelligence. Before it impacts your institution.',
} as const;

export const ANALYST_CONTENT = {
  eyebrow: 'Meet Your Lead Intelligence Analyst',
  name: 'Ken W. Sather',
  title: 'Founder & Chief Intelligence Analyst',
  portraitSrc: '/images/ken-sather.png',
  portraitAlt:
    'Professional portrait of Ken W. Sather, Founder & Chief Intelligence Analyst at HiddenAlerts',
  credentials: [
    'Former FDIC Bank Examiner',
    'Certified Regulatory Compliance Manager (CRCM)',
    'Financial Crime Investigator',
    'BSA/AML & Consumer Compliance Specialist',
    '30+ Years Banking & Financial Crime Experience',
  ],
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
  title: 'Stay Ahead of Emerging Fraud Risks',
  intro: "Every Friday you'll receive:",
  features: [
    'One Featured High-Risk Alert',
    'Weekly Fraud Intelligence Summary',
    'Analyst Commentary',
    'Intelligence Brief Preview',
    'Email Delivery',
  ],
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
  tagline: 'Early fraud intelligence. Early detection. Actionable protection.',
  newsletterTitle: 'Get Free Intelligence Updates',
  newsletterDescription:
    'Get the weekly intelligence brief and high-risk alert preview.',
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
