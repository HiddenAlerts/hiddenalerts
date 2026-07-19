/** Normalizes API `risk_level` to uppercase labels (HIGH / MEDIUM / LOW). */
export function formatRiskLevelLabel(risk: string): string {
  const r = risk.trim().toLowerCase();
  if (r === 'high') return 'HIGH';
  if (r === 'medium') return 'MEDIUM';
  if (r === 'low') return 'LOW';
  return risk.trim().toUpperCase();
}

/**
 * Subscriber Critical/High badge from V1 `risk_band` only.
 * Do not use legacy `risk_level` — it cannot distinguish Critical from High
 * (e.g. score 80 may be risk_level=high + risk_band=critical).
 */
export function getRiskBandBadgeLabel(
  riskBand?: string | null,
  _riskLevel?: string | null,
): string | null {
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
export function formatRiskBandLabel(
  riskBand?: string | null,
  riskLevel?: string | null,
): string {
  const badge = getRiskBandBadgeLabel(riskBand);
  if (badge) return formatRiskBandBadgeText(badge);
  // Prefer V1 band copy; only fall back to legacy level when band is absent.
  const band = riskBand?.trim().toLowerCase();
  if (band === 'medium') return 'Medium';
  if (band === 'below_60') return 'Below 60';
  if (band) {
    return band.replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
  }
  const level = riskLevel?.trim().toLowerCase();
  if (level === 'medium') return 'Medium';
  if (level === 'low') return 'Low';
  if (level === 'high') return 'High';
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

export type BackendAlertRiskClassification =
  | 'critical'
  | 'high'
  | 'medium'
  | 'low'
  | 'below_60';

/**
 * Resolves V1 classification for filters / tones.
 * Prefer `risk_band`. Legacy `risk_level` is only a fallback when band is absent
 * (and cannot represent Critical).
 */
export function resolveAlertRiskBand(
  riskBand: string | null | undefined,
  riskLevel?: string | null,
): BackendAlertRiskClassification | null {
  const band = riskBand?.trim().toLowerCase();
  if (
    band === 'critical' ||
    band === 'high' ||
    band === 'medium' ||
    band === 'low' ||
    band === 'below_60'
  ) {
    return band;
  }
  const level = riskLevel?.trim().toLowerCase();
  // Legacy 3-level: high/medium/low — never invent Critical from risk_level.
  if (level === 'high') return 'high';
  if (level === 'medium') return 'medium';
  if (level === 'low') return 'low';
  return null;
}

export function riskBandToScoreVisualTone(
  band: BackendAlertRiskClassification | null,
): ScoreVisualTone {
  if (band === 'critical' || band === 'high') return 'danger';
  if (band === 'medium') return 'warning';
  if (band === 'low') return 'success';
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

/** Large score color derived only from backend classification fields. */
export function scoreVisualTone(
  riskLevelLabel: string,
  riskBand?: string | null,
): ScoreVisualTone {
  const resolved = resolveAlertRiskBand(riskBand, riskLevelLabel);
  if (resolved) return riskBandToScoreVisualTone(resolved);

  const u = riskLevelLabel.toUpperCase();
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
