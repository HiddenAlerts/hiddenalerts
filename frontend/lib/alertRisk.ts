import type { AlertItem } from '@/types/alert';

export type AlertRiskLevel = 'high' | 'medium' | 'low';

/** Maps backend classification fields to dashboard risk columns. */
export function getAlertRisk(alert: AlertItem): AlertRiskLevel {
  const band = alert.riskBand?.trim().toLowerCase();
  if (
    band === 'critical' ||
    band === 'high' ||
    alert.riskBandLabel === 'HIGH' ||
    alert.riskBandLabel === 'CRITICAL'
  ) {
    return 'high';
  }
  const level = alert.riskLevelLabel.trim().toLowerCase();
  if (level === 'critical' || level === 'high') return 'high';
  if (level === 'medium') return 'medium';
  return 'low';
}

export function partitionAlertsByRisk(alerts: AlertItem[]) {
  const high: AlertItem[] = [];
  const medium: AlertItem[] = [];
  const low: AlertItem[] = [];
  for (const alert of alerts) {
    const level = getAlertRisk(alert);
    if (level === 'high') high.push(alert);
    else if (level === 'medium') medium.push(alert);
    else low.push(alert);
  }
  return { high, medium, low };
}
