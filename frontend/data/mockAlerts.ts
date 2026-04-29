import type { AlertItem } from '@/types/alert';

export const MOCK_ALERTS: AlertItem[] = [
  {
    id: '1',
    title: 'Unusual login activity',
    description:
      'Multiple failed sign-in attempts from a new region were detected on your account.',
    sourceLabel: 'Security',
    badgeTone: 'danger',
    riskLevelLabel: 'HIGH',
    signalScore: 14,
    sourceUrl: 'https://example.com',
    category: 'security',
    occurredAt: '2026-05-25T22:00:00.000Z',
  },
  {
    id: '2',
    title: 'Report export completed',
    description:
      'Your scheduled intelligence export finished successfully and is ready to download.',
    sourceLabel: 'System',
    badgeTone: 'success',
    riskLevelLabel: 'LOW',
    sourceUrl: 'https://example.com',
    category: 'system',
    occurredAt: '2026-05-24T14:30:00.000Z',
  },
  {
    id: '3',
    title: 'New data source connected',
    description:
      'The RSS feed you added is now ingesting items and will appear in the next sync.',
    sourceLabel: 'Network',
    badgeTone: 'info',
    riskLevelLabel: 'LOW',
    sourceUrl: 'https://example.com',
    category: 'network',
    occurredAt: '2026-05-23T09:15:00.000Z',
  },
  {
    id: '4',
    title: 'Quota approaching limit',
    description:
      'You have used 85% of your monthly alert quota. Consider upgrading your plan.',
    sourceLabel: 'System',
    badgeTone: 'warning',
    riskLevelLabel: 'MEDIUM',
    signalScore: 9,
    sourceUrl: 'https://example.com',
    category: 'system',
    occurredAt: '2026-05-22T18:45:00.000Z',
  },
  {
    id: '5',
    title: 'API key rotated',
    description:
      'An administrator rotated the production API key. Update your integrations if needed.',
    sourceLabel: 'Security',
    badgeTone: 'danger',
    riskLevelLabel: 'HIGH',
    sourceUrl: 'https://example.com',
    category: 'security',
    occurredAt: '2026-05-21T11:00:00.000Z',
  },
  {
    id: '6',
    title: 'Weekly digest sent',
    description:
      'The weekly summary email was delivered to all subscribers on your workspace.',
    sourceLabel: 'System',
    badgeTone: 'success',
    riskLevelLabel: 'LOW',
    sourceUrl: 'https://example.com',
    category: 'system',
    occurredAt: '2026-05-20T08:00:00.000Z',
  },
  {
    id: '7',
    title: 'Webhook delivery failures',
    description:
      'Three consecutive delivery attempts to your endpoint failed with HTTP 502.',
    sourceLabel: 'Network',
    badgeTone: 'warning',
    riskLevelLabel: 'MEDIUM',
    signalScore: 11,
    sourceUrl: 'https://example.com',
    category: 'network',
    occurredAt: '2026-05-19T16:20:00.000Z',
  },
  {
    id: '8',
    title: 'Policy review due',
    description:
      'Your workspace data retention policy is due for review within the next fourteen days.',
    sourceLabel: 'System',
    badgeTone: 'info',
    riskLevelLabel: 'LOW',
    sourceUrl: 'https://example.com',
    category: 'system',
    occurredAt: '2026-05-18T12:00:00.000Z',
  },
];

export const ALERT_CATEGORY_OPTIONS = [
  { value: 'all', label: 'All categories' },
  { value: 'security', label: 'Security' },
  { value: 'system', label: 'System' },
  { value: 'network', label: 'Network' },
] as const;

export const ALERT_SORT_OPTIONS = [
  { value: 'recent', label: 'Recent' },
  { value: 'oldest', label: 'Oldest' },
] as const;
