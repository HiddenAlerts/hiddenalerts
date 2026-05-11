/** Dashboard / Alerts footer copy — edit strings here only. */

const SUPPORT_EMAIL = 'support@covertlytics.com';
const CONTACT_EMAIL = 'contact@covertlytics.com';

export const dashboardFooterContent = {
  productAttributionBefore: 'HiddenAlerts is a product of ',
  productAttributionCompany: 'Covertlytics, LLC.',
  descriptionLine1:
    'HiddenAlerts provides signal-based intelligence derived from public data.',
  descriptionLine2:
    'For informational purposes only. Not financial or legal advice.',
  linkDisclaimerLabel: 'Disclaimer',
  linkDisclaimerHref: '/disclaimer',
  linkTermsLabel: 'Terms',
  linkTermsHref: '/terms',
  linkPrivacyLabel: 'Privacy',
  linkPrivacyHref: '/privacy',
  linkSupportLabel: 'Support',
  linkSupportEmail: SUPPORT_EMAIL,
  linkSupportHref: `mailto:${SUPPORT_EMAIL}`,
  linkContactLabel: 'Contact',
  linkContactEmail: CONTACT_EMAIL,
  linkContactHref: `mailto:${CONTACT_EMAIL}`,
  lastUpdatedLabel: 'Last updated:',
  lastUpdated: 'May 2026',
  copyrightPrefix: '© 2026 ',
  copyrightCompany: 'Covertlytics LLC',
} as const;
