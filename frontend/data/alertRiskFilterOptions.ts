import { resolveAlertRiskBand } from '@/lib/alertDisplay';
import type { AlertApiRecord } from '@/types/alertsApi';

/**
 * Subscriber alerts list risk pills (mockup: All / Critical / High only).
 * Medium & Low are out of scope for the subscriber product path.
 */
export const ALERTS_RISK_FILTER_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
] as const;

export type AlertsRiskFilterValue =
  (typeof ALERTS_RISK_FILTER_OPTIONS)[number]['value'];

/** API `risk_level` for the Critical+High pool (backend has no `critical` level filter). */
export const SUBSCRIBER_ALERTS_API_RISK_LEVEL = 'high' as const;

/** True when the alert is Critical or High by `risk_band` / score. */
export function isSubscriberVisibleAlert(record: AlertApiRecord): boolean {
  const band = resolveAlertRiskBand(record.risk_band, record.signal_score);
  return band === 'critical' || band === 'high';
}

/** Matches URL risk pill against an alert record. */
export function alertMatchesSubscriberRiskFilter(
  record: AlertApiRecord,
  risk: AlertsRiskFilterValue,
): boolean {
  const band = resolveAlertRiskBand(record.risk_band, record.signal_score);
  if (risk === 'all') return band === 'critical' || band === 'high';
  if (risk === 'critical') return band === 'critical';
  if (risk === 'high') return band === 'high';
  return false;
}
