import type {
  DashboardTopAlertWeeklyIcon,
  DashboardTopAlertWeeklyItem,
  DashboardTopAlertWeeklyRiskTone,
} from '@/data/dashboardTopAlertsThisWeek';
import { resolveAlertRiskBand } from '@/lib/alertDisplay';
import type { AlertApiRecord } from '@/types/alertsApi';

/** Window (ms) within which an alert is flagged as "NEW" relative to `now`. */
const NEW_ALERT_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

type RiskPresentation = {
  tone: DashboardTopAlertWeeklyRiskTone;
  label: string;
};

/** Maps backend classification to dashboard presentation; never infers from score. */
function mapBackendRiskToWeeklyRisk(record: AlertApiRecord): RiskPresentation {
  const band = resolveAlertRiskBand(record.risk_band, record.risk_level);
  if (band === 'critical') {
    return {
      tone: 'critical',
      label: 'Critical Risk',
    };
  }
  if (band === 'high') {
    return {
      tone: 'high',
      label: 'High Risk',
    };
  }
  return {
    tone: 'medium',
    label:
      band === 'low' || band === 'below_60'
        ? 'Low Risk'
        : band === 'medium'
          ? 'Medium Risk'
          : 'Risk',
  };
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

  const risk = mapBackendRiskToWeeklyRisk(record);

  // Category + source only (avoid repeating title-like headlines in the row).
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
    description: record.summary?.trim() || '',
    riskScore: record.signal_score,
    riskTone: risk.tone,
    riskLabel: risk.tone === 'critical' ? 'CRITICAL' : risk.tone === 'high' ? 'HIGH' : risk.label,
    riskRange: '',
    iconType: mapCategoryToWeeklyIcon(record.category),
    isNew,
    occurredAtIso,
    href,
  };
}
