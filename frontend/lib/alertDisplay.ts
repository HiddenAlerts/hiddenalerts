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
