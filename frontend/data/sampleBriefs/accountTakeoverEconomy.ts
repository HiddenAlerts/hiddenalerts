/**
 * Source content for sample Intelligence Brief #1 (Ken / client).
 * Landing teaser uses a short preview only — see `INTELLIGENCE_BRIEF_PREVIEW` in `data/landing.ts`.
 * Full narrative is for Elementor public page + CMS when publishing this brief.
 */

export const ACCOUNT_TAKEOVER_ECONOMY_BRIEF = {
  title:
    'The Account Takeover Economy: How Criminal Networks Are Targeting Mobile Banking',
  riskScore: 80,
  riskLevel: 'Critical',
  publishedLabel: 'June 10, 2026',
  category: 'Financial Crime',
  categoriesLabel: 'Cybercrime • Financial Crime',
  thumbnailSrc: '/images/briefs/account-takeover-economy.png',
  sourceCount: 11,
  timeHorizon: '6 – 12 Months',
  /**
   * Landing preview Executive Summary — first two sentences from the
   * published brief (Ken: keep preview to two sentences).
   */
  landingPreviewSummary:
    'Account takeover attacks continue to increase as organized criminal groups industrialize credential theft and underground account marketplaces. Financial institutions face growing exposure from phishing, SIM swapping, malware, and credential resale operations.',
  threatSnapshot: [
    'Financial institutions are experiencing a sustained increase in account takeover (ATO) attempts targeting mobile banking applications. Criminal actors are leveraging stolen credentials, phishing campaigns, Infostealer Malware, SIM swapping, social engineering, and credential marketplaces to gain unauthorized access to customer accounts.',
    'The growing adoption of mobile banking has shifted fraud activity toward mobile platforms, which now serve as a primary access point for consumers to manage accounts, transfer funds, and conduct financial transactions.',
    'Organized fraud networks increasingly combine stolen credentials with personally identifiable information (PII), device data, and social engineering tactics to bypass authentication controls and execute fraudulent transactions.',
  ],
  whyThisMatters: [
    'Mobile banking applications have become a preferred target because they provide direct access to customer funds, personal information, and payment services. Successful account takeover attacks can result in financial losses, customer reimbursement costs, regulatory scrutiny, reputational damage, and increased fraud investigation workloads.',
    'As digital banking adoption continues to expand, account takeover activity is expected to remain one of the most persistent threats facing banks, credit unions, fintech platforms, and their customers.',
  ],
  keyFindings: [
    'Mobile banking has become the preferred access channel for many consumers, increasing exposure to account takeover activity.',
    'Credential theft remains the primary enabler of mobile banking fraud.',
    'Criminal marketplaces increasingly provide complete account-access packages rather than standalone credentials.',
    'Fraud actors are combining phishing, malware, SIM swapping, and social engineering to bypass authentication controls.',
    'Account takeover activity is becoming increasingly industrialized and scalable.',
  ],
  businessImpact: [
    'Customer reimbursement costs',
    'Increased fraud losses',
    'Regulatory scrutiny',
    'Operational investigation costs',
    'Brand and reputation damage',
    'Increased customer churn',
  ],
  keySignals: [
    'Increased reports of unauthorized access to mobile banking accounts.',
    'Growth in credential theft campaigns targeting banking customers.',
    'Expansion of phishing and smishing campaigns impersonating financial institutions.',
    'Increased availability of banking credentials for sale on underground forums.',
    'Rising use of SIM swapping and multi-factor authentication bypass techniques.',
    'Greater use of mobile malware designed to harvest banking credentials and session tokens.',
    'Increased fraud losses associated with account takeover incidents.',
  ],
  keyActors: [
    {
      name: 'Credential Brokers',
      description:
        'Threat actors specializing in acquiring and selling stolen banking credentials obtained through malware infections, phishing campaigns, and data breaches.',
    },
    {
      name: 'Account Takeover Groups',
      description:
        'Criminal organizations that purchase stolen credentials and exploit compromised accounts for financial gain.',
    },
    {
      name: 'Phishing and Smishing Operators',
      description:
        'Fraud actors conducting email and text-message campaigns designed to capture banking credentials and authentication codes.',
    },
    {
      name: 'SIM Swapping Networks',
      description:
        'Criminal actors targeting mobile carriers to hijack customer phone numbers and intercept authentication messages.',
    },
    {
      name: 'Money Mule Networks',
      description:
        'Individuals and organized groups responsible for receiving and laundering proceeds generated through account takeover fraud.',
    },
  ],
} as const;
