import type { BriefRiskLabel } from '@/types/briefs';

/** Maps a 0-100 risk score to its labelled band. */
export function riskScoreToLabel(score: number): BriefRiskLabel {
  if (score >= 80) return 'Critical';
  if (score >= 60) return 'High';
  if (score >= 40) return 'Medium';
  return 'Low';
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
