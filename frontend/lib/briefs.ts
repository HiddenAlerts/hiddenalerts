import type { BriefDetailRiskLevel, BriefRiskLabel } from '@/types/briefs';

/**
 * Brief score bands (aligned with alert Critical/High/Medium thresholds).
 * CMS risk_level should stay in sync with these when score is set.
 */
export const BRIEF_SCORE_THRESHOLDS = {
  critical: 81,
  high: 71,
  medium: 61,
} as const;

/** Maps a 0–100 risk score to its labelled band. */
export function riskScoreToLabel(score: number): BriefRiskLabel {
  if (score >= BRIEF_SCORE_THRESHOLDS.critical) return 'Critical';
  if (score >= BRIEF_SCORE_THRESHOLDS.high) return 'High';
  if (score >= BRIEF_SCORE_THRESHOLDS.medium) return 'Medium';
  return 'Low';
}

/** Maps a 0–100 score to the API/admin risk_level enum. */
export function riskScoreToDetailLevel(score: number): BriefDetailRiskLevel {
  if (score >= BRIEF_SCORE_THRESHOLDS.critical) return 'critical';
  if (score >= BRIEF_SCORE_THRESHOLDS.high) return 'high';
  if (score >= BRIEF_SCORE_THRESHOLDS.medium) return 'medium';
  return 'low';
}

/**
 * Prefer numeric score for the badge when present (> 0).
 * Falls back to API `risk_level` so older rows still show a band.
 */
export function resolveBriefRiskLabel(
  score: number | null | undefined,
  apiLevel: BriefDetailRiskLevel | string | null | undefined,
): BriefRiskLabel {
  if (typeof score === 'number' && Number.isFinite(score) && score > 0) {
    return riskScoreToLabel(score);
  }
  const level = apiLevel?.trim().toLowerCase();
  if (level === 'critical') return 'Critical';
  if (level === 'high') return 'High';
  if (level === 'medium') return 'Medium';
  if (level === 'low') return 'Low';
  return 'Low';
}

/** Card/detail display — never invent a fake mid-scale placeholder. */
export function formatBriefRiskScore(score: number | null | undefined): string {
  if (typeof score !== 'number' || !Number.isFinite(score) || score <= 0) {
    return '—';
  }
  return `${Math.round(score)}/100`;
}

export type BriefLibraryStats = {
  total: number;
  critical: number;
  high: number;
};

export function formatBriefDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
