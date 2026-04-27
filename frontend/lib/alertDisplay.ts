/** Normalizes API `risk_level` to uppercase labels (HIGH / MEDIUM / LOW). */
export function formatRiskLevelLabel(risk: string): string {
  const r = risk.trim().toLowerCase();
  if (r === 'high') return 'HIGH';
  if (r === 'medium') return 'MEDIUM';
  if (r === 'low') return 'LOW';
  return risk.trim().toUpperCase();
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

/** Large score color: high scores red, mid orange, else neutral (mockup-style). */
export function scoreVisualTone(
  signalScore: number | undefined,
  riskLevelLabel: string,
): ScoreVisualTone {
  const u = riskLevelLabel.toUpperCase();
  if (typeof signalScore === 'number') {
    if (signalScore >= 90) return 'danger';
    if (signalScore >= 70) return 'warning';
  }
  if (u === 'HIGH') return 'danger';
  if (u === 'MEDIUM') return 'warning';
  if (u === 'LOW') return 'success';
  if (typeof signalScore === 'number' && signalScore >= 50) return 'success';
  return 'muted';
}
