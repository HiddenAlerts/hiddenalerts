import type {
  DashboardTopAlertWeeklyIcon,
  DashboardTopAlertWeeklyItem,
  DashboardTopAlertWeeklyRiskTone,
} from '@/data/dashboardTopAlertsThisWeek';
import type { AlertApiRecord } from '@/types/alertsApi';

/** Window (ms) within which an alert is flagged as "NEW" relative to `now`. */
const NEW_ALERT_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

type RiskPresentation = {
  tone: DashboardTopAlertWeeklyRiskTone;
  label: string;
  range: string;
};

/**
 * Derives the score box presentation from the numeric signal score so the
 * displayed range matches the dashboard risk tiers (Critical 80-100,
 * High 60-79, Medium below).
 */
export function mapSignalScoreToWeeklyRisk(score: number): RiskPresentation {
  if (score >= 80) {
    return { tone: 'critical', label: 'Critical Risk', range: '80-100' };
  }
  if (score >= 60) {
    return { tone: 'high', label: 'High Risk', range: '60-79' };
  }
  return { tone: 'medium', label: 'Medium Risk', range: '0-59' };
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

  const risk = mapSignalScoreToWeeklyRisk(record.signal_score);

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
