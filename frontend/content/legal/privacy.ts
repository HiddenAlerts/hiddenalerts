import type { LegalPageDocument } from './types';

export const privacyDocument: LegalPageDocument = {
  title: 'Privacy Policy',
  lastUpdated: 'May 2026',
  blocks: [
    {
      type: 'paragraph',
      text: 'HiddenAlerts, a platform operated by Covertlytics LLC, respects your privacy.',
    },
    { type: 'sectionTitle', text: 'Information We Collect' },
    {
      type: 'bulletList',
      items: [
        'Email address (if provided)',
        'Basic usage data (pages viewed, interactions, device info)',
      ],
    },
    { type: 'sectionTitle', text: 'How We Use Information' },
    {
      type: 'bulletList',
      items: [
        'Operate and improve the platform',
        'Analyze usage trends',
        'Communicate updates (if subscribed)',
      ],
    },
    { type: 'sectionTitle', text: 'Data Sharing' },
    {
      type: 'paragraph',
      text: 'We do not sell personal data.',
    },
    {
      type: 'paragraph',
      text: 'Data may be shared with service providers for platform operation.',
    },
    { type: 'sectionTitle', text: 'Data Security' },
    {
      type: 'paragraph',
      text: 'We use reasonable safeguards, but no system is fully secure.',
    },
    { type: 'sectionTitle', text: 'User Responsibility' },
    {
      type: 'paragraph',
      text: 'You are responsible for maintaining account confidentiality.',
    },
    { type: 'sectionTitle', text: 'Changes' },
    {
      type: 'paragraph',
      text: 'This policy may be updated. Continued use indicates acceptance.',
    },
  ],
};
