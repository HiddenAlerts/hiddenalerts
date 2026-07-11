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
  /** Legacy 3-level label (HIGH / MEDIUM / LOW) — use `riskBandLabel` for badges. */
  riskLevelLabel: string;
  /** Badge label from `risk_band` (`CRITICAL` / `HIGH`), or null when no badge. */
  riskBandLabel: string | null;
  /** Raw API `risk_band` value when present. */
  riskBand?: string;
  /** From API when available */
  signalScore?: number;
  /** External link for “View Full Signal” (from API `source_url`). */
  sourceUrl?: string;
  /** Used for the category filter */
  category: string;
  occurredAt: string;
  /** From API `source_published_at` when set; drives source-facing date/time in lists. */
  sourcePublishedAt?: string;
  /** From entity-aware search (`matched_entity`); omitted when absent or keyword match. */
  matchedEntity?: string;
};
