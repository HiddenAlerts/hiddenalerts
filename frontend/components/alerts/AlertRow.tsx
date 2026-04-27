'use client';

import {
  confidenceLabelFromRisk,
  scoreVisualTone,
  type ScoreVisualTone,
} from '@/lib/alertDisplay';
import { formatAlertDate, formatRelativeTime } from '@/lib/formatAlertDate';
import { cn } from '@/lib/utils';
import type { AlertItem } from '@/types/alert';
import type { FC } from 'react';

const toneText: Record<ScoreVisualTone, string> = {
  danger: 'text-danger',
  warning: 'text-warning',
  success: 'text-success',
  muted: 'text-body',
};

function RiskBadge({ label }: { label: string }) {
  const base =
    'inline-flex shrink-0 items-center rounded-md border px-2.5 py-1 text-xs font-bold uppercase tracking-wide';
  if (label === 'HIGH') {
    return (
      <span
        className={cn(
          base,
          'border-danger/55 bg-danger/18 text-danger',
        )}
      >
        {label}
      </span>
    );
  }
  if (label === 'MEDIUM') {
    return (
      <span
        className={cn(
          base,
          'border-warning/55 bg-warning/18 text-warning',
        )}
      >
        {label}
      </span>
    );
  }
  if (label === 'LOW') {
    return (
      <span
        className={cn(
          base,
          'border-success/50 bg-success/14 text-success',
        )}
      >
        {label}
      </span>
    );
  }
  return (
    <span
      className={cn(
        base,
        'border-border bg-surface-muted/45 text-muted',
      )}
    >
      {label}
    </span>
  );
}

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
  const headline = alert.title.trim();
  const confidence = confidenceLabelFromRisk(alert.riskLevelLabel);
  const categoryLabel = formatCategoryLabel(alert.category);
  const tone = scoreVisualTone(alert.signalScore, alert.riskLevelLabel);
  const scoreToneClass = toneText[tone];

  const metadataParts = [
    sourceShort,
    relativeTime,
    categoryLabel,
    `Confidence: ${confidence}`,
  ];

  const cardSurface = cn(
    'border-border bg-surface/42 rounded-lg border p-4',
    'border-l-2',
    cardAccentClass(alert.riskLevelLabel),
    'transition-all duration-200',
    'hover:-translate-y-0.5 hover:border-primary-500/40 hover:bg-surface/58 hover:shadow-md',
    alert.sourceUrl &&
      'cursor-pointer focus-visible:ring-primary-500/35 focus-visible:ring-2 focus-visible:outline-none',
  );

  const inner = (
    <>
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-wrap items-center gap-2.5">
          <RiskBadge label={alert.riskLevelLabel} />
          <span
            className="text-body text-sm font-medium"
            title={absoluteTime}
          >
            {relativeTime}
          </span>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-muted text-[0.7rem] font-semibold tracking-wide uppercase">
            Score
          </div>
          <div
            className={cn(
              'mt-0.5 text-4xl leading-none font-bold tabular-nums tracking-tight',
              scoreToneClass,
            )}
          >
            {typeof alert.signalScore === 'number' ? alert.signalScore : '—'}
          </div>
        </div>
      </div>

      <h2 className="font-heading text-foreground mt-3 line-clamp-2 text-lg leading-snug font-semibold tracking-tight sm:text-xl">
        {headline}
      </h2>

      <p className="text-body mt-2 line-clamp-2 text-[0.98rem] leading-relaxed">
        {summary}
      </p>

      <div className="border-border/70 mt-3 flex flex-col gap-2 border-t pt-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <p
          className="text-body min-w-0 flex-1 text-sm leading-relaxed tracking-[0.01em]"
          title={metadataParts.join(' • ')}
        >
          {metadataParts.map((part, index) => (
            <span key={`${part}-${index}`}>
              {index > 0 ? <span className="mx-2.5 text-muted">•</span> : null}
              {part}
            </span>
          ))}
        </p>
        {alert.sourceUrl ? (
          <span
            className={cn(
              'shrink-0 text-[0.95rem] font-semibold whitespace-nowrap',
              scoreToneClass,
            )}
          >
            View Signal →
          </span>
        ) : null}
      </div>
    </>
  );

  if (alert.sourceUrl) {
    return (
      <a
        href={alert.sourceUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(cardSurface, className)}
      >
        {inner}
      </a>
    );
  }

  return <article className={cn(cardSurface, className)}>{inner}</article>;
};
