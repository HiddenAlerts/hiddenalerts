import type { AlertItem } from '@/types/alert';

export type AlertRiskLevel = 'high' | 'medium' | 'low';

/** Maps existing badge tones to dashboard risk columns without changing alert data. */
export function getAlertRisk(alert: AlertItem): AlertRiskLevel {
  switch (alert.badgeTone) {
    case 'danger':
      return 'high';
    case 'warning':
      return 'medium';
    default:
      return 'low';
  }
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
