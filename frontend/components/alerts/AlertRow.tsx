'use client';

import {
  type ScoreVisualTone,
  confidenceLabelFromRisk,
  scoreVisualTone,
  truncateSignalHeadline,
} from '@/lib/alertDisplay';
import { formatAlertDate, formatRelativeTime } from '@/lib/formatAlertDate';
import { cn } from '@/lib/utils';
import type { AlertItem } from '@/types/alert';
import Link from 'next/link';
import type { FC } from 'react';

import { RiskBadge } from './RiskBadge';

const toneText: Record<ScoreVisualTone, string> = {
  danger: 'text-danger',
  warning: 'text-warning',
  success: 'text-success',
  muted: 'text-body',
};

function cardAccentClass(label: string) {
  if (label === 'HIGH') return 'border-l-danger';
  if (label === 'MEDIUM') return 'border-l-warning';
  if (label === 'LOW') return 'border-l-success';
  return 'border-l-border';
}

function formatCategoryLabel(category: string) {
  if (!category) return category;
  return category.replace(/\b\w/g, ch => ch.toUpperCase());
}

export type AlertRowProps = {
  alert: AlertItem;
  className?: string;
};

export const AlertRow: FC<AlertRowProps> = ({ alert, className }) => {
  const sourceShort = alert.sourceDisplayLabel ?? alert.sourceLabel;
  const summary = alert.description;
  const relativeTime = formatRelativeTime(alert.occurredAt);
  const absoluteTime = formatAlertDate(alert.occurredAt);
  const headline = truncateSignalHeadline(alert.title, 10);
  const confidence = confidenceLabelFromRisk(alert.riskLevelLabel);
  const categoryLabel = formatCategoryLabel(alert.category);
  const tone = scoreVisualTone(alert.signalScore, alert.riskLevelLabel);
  const scoreToneClass = toneText[tone];

  const metadataLine = [
    sourceShort,
    relativeTime,
    categoryLabel,
    `Confidence ${confidence}`,
  ].join(' • ');

  const cardSurface = cn(
    'border-border bg-surface/42 rounded-lg border p-4',
    'border-l-2',
    cardAccentClass(alert.riskLevelLabel),
    'transition-all duration-200',
    'hover:-translate-y-1 hover:border-primary-500/45 hover:bg-surface/62 hover:shadow-lg hover:shadow-black/25',
    'cursor-pointer focus-visible:ring-primary-500/35 focus-visible:ring-2 focus-visible:outline-none',
  );

  const inner = (
    <div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_112px] sm:gap-6">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-2.5">
            <RiskBadge label={alert.riskLevelLabel} />
            <span
              className="text-body text-sm font-medium"
              title={absoluteTime}
            >
              {relativeTime}
            </span>
          </div>

          <h2 className="font-heading text-foreground mt-3 line-clamp-2 text-lg leading-snug font-semibold tracking-tight sm:text-[1.1rem]">
            {headline}
          </h2>

          <p className="text-body mt-2 line-clamp-2 text-[0.98rem] leading-relaxed">
            {summary}
          </p>
        </div>

        <div className="flex items-end justify-between gap-3 p-4 pt-1 sm:min-h-full sm:flex-col sm:items-end sm:justify-start sm:pl-3">
          <div className="shrink-0 text-right">
            <div className="text-muted text-[0.7rem] font-semibold tracking-wide uppercase">
              Score
            </div>
            <div
              className={cn(
                'mt-0.5 text-4xl leading-none font-bold tracking-tight tabular-nums',
                scoreToneClass,
              )}
            >
              {typeof alert.signalScore === 'number' ? alert.signalScore : '—'}
            </div>
          </div>
        </div>
      </div>

      <div className="border-border/70 mt-3 flex items-center justify-between gap-4 border-t pt-3">
        <p
          className="text-body min-w-0 flex-1 truncate text-sm leading-relaxed tracking-[0.01em]"
          title={metadataLine}
        >
          {metadataLine}
        </p>
        <span
          className={cn(
            'shrink-0 text-[0.95rem] font-semibold whitespace-nowrap',
            scoreToneClass,
          )}
        >
          View Details →
        </span>
      </div>
    </div>
  );

  return (
    <Link href={`/alerts/${alert.id}`} className={cn(cardSurface, className)}>
      {inner}
    </Link>
  );
};
