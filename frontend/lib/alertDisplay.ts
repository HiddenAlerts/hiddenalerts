/** Normalizes API `risk_level` to uppercase labels (HIGH / MEDIUM / LOW). */
export function formatRiskLevelLabel(risk: string): string {
  const r = risk.trim().toLowerCase();
  if (r === 'high') return 'HIGH';
  if (r === 'medium') return 'MEDIUM';
  if (r === 'low') return 'LOW';
  return risk.trim().toUpperCase();
}

/** Returns CRITICAL / HIGH badge label from `risk_band`, or null when no badge. */
export function getRiskBandBadgeLabel(riskBand?: string | null): string | null {
  const band = riskBand?.trim().toLowerCase();
  if (band === 'critical') return 'CRITICAL';
  if (band === 'high') return 'HIGH';
  return null;
}

export function shouldShowRiskBadge(riskBand?: string | null): boolean {
  return getRiskBandBadgeLabel(riskBand) !== null;
}

/** Display text for badge labels (Critical / High). */
export function formatRiskBandBadgeText(label: string): string {
  if (label === 'CRITICAL') return 'Critical';
  if (label === 'HIGH') return 'High';
  return label;
}

/** Human-readable risk band for detail panels, e.g. "Critical". */
export function formatRiskBandLabel(riskBand?: string | null): string {
  const badge = getRiskBandBadgeLabel(riskBand);
  if (badge) return formatRiskBandBadgeText(badge);
  const band = riskBand?.trim().toLowerCase();
  if (band === 'medium') return 'Medium';
  if (band === 'below_60') return 'Below 60';
  if (band) {
    return band.replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
  }
  return '—';
}

/**
 * Shortens common agency/source strings for compact UI (e.g. FBI National Press Releases → FBI).
 */
export function simplifyAlertSourceName(raw: string): string {
  let s = raw.trim();
  if (!s) return s;

  s = s.replace(/\s+National\s+Press\s+Releases?$/i, '').trim();
  s = s.replace(/\s+Press\s+Releases?$/i, '').trim();
  s = s.replace(/\s+Press\s+Release$/i, '').trim();

  if (s.length > 22) {
    const first = s.split(/\s+/)[0];
    if (first && first.length >= 2) return first;
  }

  return s;
}

/** Short signal-style headline (max words, ellipsis if trimmed). */
export function truncateSignalHeadline(title: string, maxWords = 12): string {
  const words = title.trim().split(/\s+/).filter(Boolean);
  if (words.length <= maxWords) return title.trim();
  return `${words.slice(0, maxWords).join(' ')}…`;
}

export function confidenceLabelFromRisk(riskLevelLabel: string): string {
  const u = riskLevelLabel.trim().toUpperCase();
  if (u === 'HIGH') return 'High';
  if (u === 'MEDIUM') return 'Medium';
  if (u === 'LOW') return 'Low';
  return 'Unknown';
}

export type ScoreVisualTone = 'danger' | 'warning' | 'success' | 'muted';

/** Score thresholds: Critical ≥81, High ≥71, Medium ≥61. */
export const ALERT_SCORE_THRESHOLDS = {
  critical: 81,
  high: 71,
  medium: 61,
} as const;

export type AlertScoreBand = 'critical' | 'high' | 'medium' | 'below_60';

/** Derives `risk_band` from numeric score when the API omits it. */
export function scoreToRiskBand(score: number): AlertScoreBand {
  if (score >= ALERT_SCORE_THRESHOLDS.critical) return 'critical';
  if (score >= ALERT_SCORE_THRESHOLDS.high) return 'high';
  if (score >= ALERT_SCORE_THRESHOLDS.medium) return 'medium';
  return 'below_60';
}

/** Resolves the effective band from API `risk_band` or score fallback. */
export function resolveAlertRiskBand(
  riskBand: string | null | undefined,
  signalScore?: number,
): AlertScoreBand | null {
  const band = riskBand?.trim().toLowerCase();
  if (
    band === 'critical' ||
    band === 'high' ||
    band === 'medium' ||
    band === 'below_60'
  ) {
    return band;
  }
  if (typeof signalScore === 'number' && Number.isFinite(signalScore)) {
    return scoreToRiskBand(signalScore);
  }
  return null;
}

export function riskBandToScoreVisualTone(
  band: AlertScoreBand | null,
): ScoreVisualTone {
  if (band === 'critical' || band === 'high') return 'danger';
  if (band === 'medium') return 'warning';
  if (band === 'below_60') return 'muted';
  return 'muted';
}

/** Tailwind text class for large score numerals on alert detail. */
export function scoreVisualToneClass(tone: ScoreVisualTone): string {
  if (tone === 'danger') return 'text-danger';
  if (tone === 'warning') return 'text-warning';
  if (tone === 'success') return 'text-success';
  return 'text-body';
}

/** Large score color — prefers `risk_band`, then admin score thresholds. */
export function scoreVisualTone(
  signalScore: number | undefined,
  riskLevelLabel: string,
  riskBand?: string | null,
): ScoreVisualTone {
  const resolved = resolveAlertRiskBand(riskBand, signalScore);
  if (resolved) return riskBandToScoreVisualTone(resolved);

  const u = riskLevelLabel.toUpperCase();
  if (typeof signalScore === 'number') {
    return riskBandToScoreVisualTone(scoreToRiskBand(signalScore));
  }
  if (u === 'HIGH') return 'danger';
  if (u === 'MEDIUM') return 'warning';
  if (u === 'LOW') return 'success';
  return 'muted';
}

/**
 * ISO-ish instant for displaying source-facing dates in the UI:
 * prefers API `source_published_at`, otherwise ingest time (`published_at` / `occurredAt`).
 */
export function alertDisplayedAtIso(alert: {
  sourcePublishedAt?: string;
  occurredAt: string;
}): string {
  const s = alert.sourcePublishedAt?.trim();
  if (s) return s;
  return alert.occurredAt;
}

/** Newest-first ordering for compact dashboard preview lists. */
export function sortAlertsByDisplayedAtDesc<
  T extends { sourcePublishedAt?: string; occurredAt: string },
>(a: T, b: T): number {
  return alertDisplayedAtIso(b).localeCompare(alertDisplayedAtIso(a));
}
