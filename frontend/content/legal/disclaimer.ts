import type { LegalPageDocument } from './types';

export const disclaimerDocument: LegalPageDocument = {
  title: 'Disclaimer',
  lastUpdated: 'May 2026',
  blocks: [
    {
      type: 'paragraph',
      text: 'HiddenAlerts is operated by Covertlytics LLC.',
    },
    {
      type: 'paragraph',
      text: 'HiddenAlerts provides aggregated intelligence derived from publicly available information and automated analysis.',
    },
    {
      type: 'paragraph',
      text: 'The platform is designed to surface potential risk signals, patterns, and indicators for research and informational purposes only.',
    },
    { type: 'sectionTitle', text: 'HiddenAlerts does not:' },
    {
      type: 'bulletList',
      items: [
        'Make determinations of wrongdoing',
        'Assert that any entity or individual has engaged in illegal activity',
        'Provide legal, financial, or investment advice',
      ],
    },
    {
      type: 'paragraph',
      text: 'All risk scores, classifications, and summaries are generated using algorithmic models and may not reflect complete, accurate, or current information.',
    },
    {
      type: 'paragraph',
      text: 'Information may be incomplete, delayed, or subject to change as new data becomes available.',
    },
    {
      type: 'paragraph',
      text: 'HiddenAlerts does not verify all underlying sources and does not guarantee the accuracy or completeness of third-party information.',
    },
    {
      type: 'paragraph',
      text: 'The platform may include automated or AI-assisted analysis, which may produce incomplete or imperfect results.',
    },
    {
      type: 'paragraph',
      text: 'Users are solely responsible for independently verifying all information and conducting their own due diligence before making any decisions.',
    },
    {
      type: 'paragraph',
      text: 'HiddenAlerts disclaims any responsibility for actions taken based on the information presented on this platform.',
    },
    {
      type: 'paragraph',
      text: 'Use of the platform is at your own discretion and risk.',
    },
    {
      type: 'paragraph',
      text: 'HiddenAlerts operates as an intelligence aggregation and analysis platform, not an investigative or enforcement authority.',
    },
  ],
};
