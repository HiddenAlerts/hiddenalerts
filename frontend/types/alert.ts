export type AlertBadgeTone = 'danger' | 'success' | 'info' | 'warning';

export type AlertItem = {
  id: string;
  title: string;
  description: string;
  /** Shown in the Source column */
  sourceLabel: string;
  badgeTone: AlertBadgeTone;
  /** Used for the category filter */
  category: string;
  occurredAt: string;
};
