import {
  scoreToRiskBand,
} from '@/lib/alertDisplay';
import type { AlertApiRecord } from '@/types/alertsApi';

/** True when an alert is Critical or High (band, level, or score). */
export function isCriticalOrHighAlert(record: AlertApiRecord): boolean {
  const band = record.risk_band?.trim().toLowerCase();
  if (band === 'critical' || band === 'high') return true;

  const level = record.risk_level?.trim().toLowerCase();
  if (level === 'critical' || level === 'high') return true;

  // Some payloads omit band — fall back to score thresholds.
  const fromScore = scoreToRiskBand(record.signal_score);
  return fromScore === 'critical' || fromScore === 'high';
}

function alertOccurredMs(record: AlertApiRecord): number {
  const iso = record.source_published_at || record.published_at;
  const ms = new Date(iso).getTime();
  return Number.isNaN(ms) ? 0 : ms;
}

/**
 * Newest Critical & High alerts first — used by the dashboard
 * "Top Alerts This Week" section.
 */
export function pickNewestCriticalHighAlerts(
  records: AlertApiRecord[],
  limit: number,
): AlertApiRecord[] {
  return [...records]
    .filter(isCriticalOrHighAlert)
    .sort((a, b) => alertOccurredMs(b) - alertOccurredMs(a))
    .slice(0, limit);
}
