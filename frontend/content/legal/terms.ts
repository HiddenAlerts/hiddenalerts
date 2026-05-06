import type { LegalPageDocument } from './types';

export const termsDocument: LegalPageDocument = {
  title: 'Terms of Use',
  lastUpdated: 'May 2026',
  blocks: [
    {
      type: 'paragraph',
      text: 'These Terms of Use govern your access to and use of HiddenAlerts, a platform operated by Covertlytics LLC.',
    },
    {
      type: 'paragraph',
      text: 'By accessing or using HiddenAlerts, you agree to the following:',
    },
    { type: 'sectionTitle', text: 'Informational Use Only' },
    {
      type: 'paragraph',
      text: 'HiddenAlerts provides information for research and informational purposes only and should not be relied upon as the sole basis for decisions.',
    },
    { type: 'sectionTitle', text: 'No Warranties' },
    {
      type: 'paragraph',
      text: 'HiddenAlerts makes no representations or warranties regarding the accuracy, completeness, reliability, or availability of information.',
    },
    { type: 'sectionTitle', text: 'Limitation of Liability' },
    {
      type: 'paragraph',
      text: 'HiddenAlerts shall not be liable for any direct or indirect damages arising from use of the platform.',
    },
    { type: 'sectionTitle', text: 'User Responsibility' },
    {
      type: 'paragraph',
      text: 'You agree to independently verify all information and conduct your own due diligence.',
    },
    { type: 'sectionTitle', text: 'Acceptable Use' },
    {
      type: 'paragraph',
      text: 'You agree not to:',
    },
    {
      type: 'bulletList',
      items: [
        'Use the platform unlawfully',
        'Misuse or misrepresent information',
        'Attempt to disrupt or reverse engineer the platform',
      ],
    },
    { type: 'sectionTitle', text: 'Intellectual Property' },
    {
      type: 'paragraph',
      text: 'All data, analysis, and platform materials are the property of HiddenAlerts and may not be copied or reproduced without permission.',
    },
    { type: 'sectionTitle', text: 'Modifications' },
    {
      type: 'paragraph',
      text: 'HiddenAlerts may update these terms at any time.',
    },
    { type: 'sectionTitle', text: 'Termination' },
    {
      type: 'paragraph',
      text: 'Access may be suspended or terminated for misuse.',
    },
    { type: 'sectionTitle', text: 'Governing Law' },
    {
      type: 'paragraph',
      text: 'These Terms shall be governed by applicable laws of the jurisdiction of Covertlytics LLC.',
    },
    {
      type: 'paragraph',
      text: 'Continued use constitutes acceptance of these terms.',
    },
  ],
};
