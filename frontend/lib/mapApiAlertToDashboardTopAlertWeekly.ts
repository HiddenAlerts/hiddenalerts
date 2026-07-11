import type {
  DashboardTopAlertWeeklyIcon,
  DashboardTopAlertWeeklyItem,
  DashboardTopAlertWeeklyRiskTone,
} from '@/data/dashboardTopAlertsThisWeek';
import {
  ALERT_SCORE_THRESHOLDS,
  scoreToRiskBand,
} from '@/lib/alertDisplay';
import type { AlertApiRecord } from '@/types/alertsApi';

/** Window (ms) within which an alert is flagged as "NEW" relative to `now`. */
const NEW_ALERT_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

type RiskPresentation = {
  tone: DashboardTopAlertWeeklyRiskTone;
  label: string;
  range: string;
};

/**
 * Derives the score box presentation from `risk_band` when available, otherwise
 * from numeric score using aligned thresholds (81 / 71 / 61).
 */
export function mapSignalScoreToWeeklyRisk(score: number): RiskPresentation {
  const band = scoreToRiskBand(score);
  if (band === 'critical') {
    return {
      tone: 'critical',
      label: 'Critical Risk',
      range: `${ALERT_SCORE_THRESHOLDS.critical}-100`,
    };
  }
  if (band === 'high') {
    return {
      tone: 'high',
      label: 'High Risk',
      range: `${ALERT_SCORE_THRESHOLDS.high}-${ALERT_SCORE_THRESHOLDS.critical - 1}`,
    };
  }
  if (band === 'medium') {
    return {
      tone: 'medium',
      label: 'Medium Risk',
      range: `${ALERT_SCORE_THRESHOLDS.medium}-${ALERT_SCORE_THRESHOLDS.high - 1}`,
    };
  }
  return {
    tone: 'medium',
    label: 'Medium Risk',
    range: `0-${ALERT_SCORE_THRESHOLDS.medium - 1}`,
  };
}

function mapRiskBandToWeeklyRisk(record: AlertApiRecord): RiskPresentation {
  const band = record.risk_band?.trim().toLowerCase();
  if (band === 'critical') {
    return {
      tone: 'critical',
      label: 'Critical Risk',
      range: `${ALERT_SCORE_THRESHOLDS.critical}-100`,
    };
  }
  if (band === 'high') {
    return {
      tone: 'high',
      label: 'High Risk',
      range: `${ALERT_SCORE_THRESHOLDS.high}-${ALERT_SCORE_THRESHOLDS.critical - 1}`,
    };
  }
  if (band === 'medium') {
    return {
      tone: 'medium',
      label: 'Medium Risk',
      range: `${ALERT_SCORE_THRESHOLDS.medium}-${ALERT_SCORE_THRESHOLDS.high - 1}`,
    };
  }
  return mapSignalScoreToWeeklyRisk(record.signal_score);
}

export function mapCategoryToWeeklyIcon(
  category: string,
): DashboardTopAlertWeeklyIcon {
  const normalized = category.trim().toLowerCase();
  if (
    normalized.includes('scam') ||
    normalized.includes('phish') ||
    normalized.includes('caller') ||
    normalized.includes('consumer') ||
    normalized.includes('telecom') ||
    normalized.includes('vish')
  ) {
    return 'phone';
  }
  if (
    normalized.includes('identity') ||
    normalized.includes('credit') ||
    normalized.includes('transport') ||
    normalized.includes('logistic') ||
    normalized.includes('supply') ||
    normalized.includes('synthetic')
  ) {
    return 'package';
  }
  if (
    normalized.includes('money') ||
    normalized.includes('launder') ||
    normalized.includes('financ') ||
    normalized.includes('sanction') ||
    normalized.includes('bribery') ||
    normalized.includes('fraud') ||
    normalized.includes('crime') ||
    normalized.includes('crypto')
  ) {
    return 'landmark';
  }
  return 'shield';
}

export function mapApiAlertToDashboardTopAlertWeeklyItem(
  record: AlertApiRecord,
  now: number = Date.now(),
): DashboardTopAlertWeeklyItem {
  const occurredAtIso = record.source_published_at || record.published_at;
  const occurredMs = new Date(occurredAtIso).getTime();
  const isNew =
    !Number.isNaN(occurredMs) && now - occurredMs <= NEW_ALERT_WINDOW_MS;

  const risk = mapRiskBandToWeeklyRisk(record);

  const tags = [record.category, record.source_name].filter(
    (value): value is string =>
      typeof value === 'string' && value.trim().length > 0,
  );

  const href = `/alerts/${encodeURIComponent(String(record.id))}`;

  return {
    id: String(record.id),
    title: record.title,
    tags,
    headline: '',
    description: record.summary,
    riskScore: record.signal_score,
    riskTone: risk.tone,
    riskLabel: risk.label,
    riskRange: risk.range,
    iconType: mapCategoryToWeeklyIcon(record.category),
    isNew,
    occurredAtIso,
    href,
  };
}
