import { scoreToRiskBand } from '@/lib/alertDisplay';
import type { AlertApiRecord } from '@/types/alertsApi';

/** True when an alert is Critical or High (band, level, or 0–100 score). */
export function isCriticalOrHighAlert(record: AlertApiRecord): boolean {
  const band = record.risk_band?.trim().toLowerCase();
  if (band === 'critical' || band === 'high') return true;

  const level = record.risk_level?.trim().toLowerCase();
  if (level === 'critical' || level === 'high') return true;

  const fromScore = scoreToRiskBand(record.signal_score);
  return fromScore === 'critical' || fromScore === 'high';
}

function alertOccurredMs(record: AlertApiRecord): number {
  const iso = record.source_published_at || record.published_at;
  const ms = new Date(iso).getTime();
  return Number.isNaN(ms) ? 0 : ms;
}

function normalizeAlertTitle(title: string): string {
  return title.trim().toLowerCase().replace(/\s+/g, ' ');
}

/**
 * Newest Critical & High alerts for the dashboard.
 * Dedupes by id and normalized title so the same story never repeats.
 */
export function pickNewestCriticalHighAlerts(
  records: AlertApiRecord[],
  limit: number,
): AlertApiRecord[] {
  const sorted = [...records].sort(
    (a, b) => alertOccurredMs(b) - alertOccurredMs(a),
  );

  const seenIds = new Set<string>();
  const seenTitles = new Set<string>();
  const picked: AlertApiRecord[] = [];

  for (const record of sorted) {
    if (!isCriticalOrHighAlert(record)) continue;

    const id = String(record.id);
    const titleKey = normalizeAlertTitle(record.title || '');
    if (seenIds.has(id)) continue;
    if (titleKey && seenTitles.has(titleKey)) continue;

    seenIds.add(id);
    if (titleKey) seenTitles.add(titleKey);
    picked.push(record);

    if (picked.length >= limit) break;
  }

  return picked;
}
