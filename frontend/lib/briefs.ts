import type { BriefDetailRiskLevel, BriefRiskLabel } from '@/types/briefs';

/**
 * Formats the classification supplied by the backend. Numeric scores are
 * intentionally not used to infer a risk level in the frontend.
 */
export function resolveBriefRiskLabel(
  apiLevel: BriefDetailRiskLevel | string | null | undefined,
): BriefRiskLabel {
  const level = apiLevel?.trim().toLowerCase();
  if (level === 'critical') return 'Critical';
  if (level === 'high') return 'High';
  if (level === 'medium') return 'Medium';
  if (level === 'low') return 'Low';
  return 'Unknown';
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
