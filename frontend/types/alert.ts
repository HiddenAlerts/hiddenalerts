export type AlertBadgeTone = 'danger' | 'success' | 'info' | 'warning';

export type AlertItem = {
  id: string;
  title: string;
  description: string;
  /** Full source name (e.g. for tooltips). */
  sourceLabel: string;
  /** Short label for the source tag when set; otherwise `sourceLabel` is used. */
  sourceDisplayLabel?: string;
  badgeTone: AlertBadgeTone;
  /** Uppercase label for UI, e.g. HIGH, MEDIUM, LOW */
  riskLevelLabel: string;
  /** From API when available */
  signalScore?: number;
  /** Used for the category filter */
  category: string;
  occurredAt: string;
};
