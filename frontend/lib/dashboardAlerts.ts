import type { AlertApiRecord } from '@/types/alertsApi';

/** True when backend classification marks an alert Critical or High. */
export function isCriticalOrHighAlert(record: AlertApiRecord): boolean {
  const band = record.risk_band?.trim().toLowerCase();
  if (band === 'critical' || band === 'high') return true;

  const level = record.risk_level?.trim().toLowerCase();
  return level === 'critical' || level === 'high';
}

/** HiddenAlerts `published_at` for ordering — never source_published_at. */
function alertPublishedMs(record: AlertApiRecord): number {
  const iso = record.published_at;
  if (!iso) return 0;
  const ms = new Date(iso).getTime();
  return Number.isNaN(ms) ? 0 : ms;
}

function normalizeAlertTitle(title: string): string {
  return title.trim().toLowerCase().replace(/\s+/g, ' ');
}

/**
 * Newest Critical & High alerts for the dashboard.
 * Orders by HiddenAlerts `published_at` DESC (same as Published feed), then
 * dedupes by id and normalized title. Does not use source_published_at.
 */
export function pickNewestCriticalHighAlerts(
  records: AlertApiRecord[],
  limit: number,
): AlertApiRecord[] {
  const sorted = [...records].sort(
    (a, b) => alertPublishedMs(b) - alertPublishedMs(a),
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
