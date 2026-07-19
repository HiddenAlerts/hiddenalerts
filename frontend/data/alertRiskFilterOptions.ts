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

/**
 * Maps the UI risk pill to the subscriber list `risk_level` query param.
 * Backend V1 bands are mutually exclusive: critical / high / medium / low.
 * - critical → risk_level=critical
 * - high → risk_level=high
 * - all → omit param (published Critical+High pool; client still filters)
 */
export function subscriberAlertsApiRiskLevel(
  risk: AlertsRiskFilterValue | string,
): 'critical' | 'high' | undefined {
  if (risk === 'critical' || risk === 'high') return risk;
  return undefined;
}

/** True when backend classification marks the alert Critical or High. */
export function isSubscriberVisibleAlert(record: AlertApiRecord): boolean {
  const band = resolveAlertRiskBand(record.risk_band, record.risk_level);
  return band === 'critical' || band === 'high';
}

/** Matches URL risk pill against an alert record. */
export function alertMatchesSubscriberRiskFilter(
  record: AlertApiRecord,
  risk: AlertsRiskFilterValue,
): boolean {
  const band = resolveAlertRiskBand(record.risk_band, record.risk_level);
  if (risk === 'all') return band === 'critical' || band === 'high';
  if (risk === 'critical') return band === 'critical';
  if (risk === 'high') return band === 'high';
  return false;
}
