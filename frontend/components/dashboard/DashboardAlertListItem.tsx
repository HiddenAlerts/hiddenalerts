'use client';

import { confidenceLabelFromRisk, scoreVisualTone } from '@/lib/alertDisplay';
import {
  DashboardCategoryIcon,
  formatDashboardAlertTypeLabel,
} from '@/lib/dashboardAlertPresentation';
import {
  formatDashboardAlertDateOnlyUtc,
  formatDashboardAlertTimeUtcLine,
} from '@/lib/formatDashboardDate';
import { cn } from '@/lib/utils';
import type { AlertItem } from '@/types/alert';
import { Bookmark, Calendar, MoreVertical } from 'lucide-react';
import Link from 'next/link';
import type { FC, MouseEvent } from 'react';

const scoreToneClass = {
  danger: 'text-danger',
  warning: 'text-warning',
  success: 'text-success',
  muted: 'text-body',
} as const;

function cardAccentClass(label: string) {
  if (label === 'HIGH') return 'border-l-danger';
  if (label === 'MEDIUM') return 'border-l-warning';
  if (label === 'LOW') return 'border-l-success';
  return 'border-l-border';
}

function cardHoverBorderClass(label: string) {
  if (label === 'HIGH') return 'hover:border-danger';
  if (label === 'MEDIUM') return 'hover:border-warning';
  if (label === 'LOW') return 'hover:border-success';
  return 'hover:border-primary-500/45';
}

function iconWellClass(label: string) {
  if (label === 'HIGH') return 'bg-danger-muted text-danger';
  if (label === 'MEDIUM') return 'bg-warning-muted text-warning';
  if (label === 'LOW') return 'bg-success-muted text-success';
  return 'bg-surface-muted text-body';
}

export type DashboardAlertListItemProps = {
  alert: AlertItem;
  className?: string;
};

function stopNavigation(e: MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
}

function MetadataPipe() {
  return (
    <span className="text-muted-foreground shrink-0 px-1 text-xs font-light">
      |
    </span>
  );
}

export const DashboardAlertListItem: FC<DashboardAlertListItemProps> = ({
  alert,
  className,
}) => {
  const tone = scoreVisualTone(alert.signalScore, alert.riskLevelLabel);
  const scoreClass = scoreToneClass[tone];
  const typeLabel = formatDashboardAlertTypeLabel(alert.category);
  const sourceShort = alert.sourceDisplayLabel ?? alert.sourceLabel;
  const scoreDisplay =
    typeof alert.signalScore === 'number' ? String(alert.signalScore) : '—';
  const riskWord = confidenceLabelFromRisk(alert.riskLevelLabel);
  const dateLine = formatDashboardAlertDateOnlyUtc(alert.occurredAt);
  const timeLine = formatDashboardAlertTimeUtcLine(alert.occurredAt);

  const scorePhrase =
    scoreDisplay === '—'
      ? `Risk score: ${scoreDisplay} (${riskWord})`
      : `Risk score: ${scoreDisplay}/100 (${riskWord})`;

  const dateTimeBlock = (
    <div className="flex shrink-0 items-center gap-2">
      <Calendar
        className="text-muted size-5 shrink-0"
        strokeWidth={1.5}
        aria-hidden
      />
      <div className="min-w-0 text-left">
        <p className="text-body text-sm leading-tight font-medium">
          {dateLine}
        </p>
        <p className="text-muted-foreground mt-0.5 text-xs leading-tight">
          {timeLine}
        </p>
      </div>
    </div>
  );

  return (
    <div
      className={cn(
        'border-border bg-background-alt group relative flex overflow-hidden rounded-lg border border-l-[3px] shadow-xs transition-colors',
        cardAccentClass(alert.riskLevelLabel),
        cardHoverBorderClass(alert.riskLevelLabel),
        className,
      )}
    >
      <Link
        href={`/alerts/${alert.id}`}
        className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 py-3 pr-2 pl-3 sm:gap-4 sm:py-3.5 sm:pr-3 sm:pl-4"
      >
        <div
          className={cn(
            'flex size-10 shrink-0 items-center justify-center rounded-full sm:size-16',
            iconWellClass(alert.riskLevelLabel),
          )}
        >
          <DashboardCategoryIcon
            category={alert.category}
            className="size-[18px] sm:size-7"
          />
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="font-heading text-foreground line-clamp-2 text-base font-semibold tracking-tight">
            {alert.title}
          </h3>

          <div className="text-muted mt-1 flex flex-wrap items-center gap-3 text-xs font-medium">
            <span
              className={cn('inline-flex flex-wrap items-center', scoreClass)}
            >
              {scorePhrase}
            </span>
            <MetadataPipe />
            <div>
              <span className="text-muted shrink-0">Type:</span>
              <span className="text-foreground ml-1">{typeLabel}</span>
            </div>
            <MetadataPipe />
            <div>
              <span className="text-muted shrink-0">Source:</span>
              <span className="text-foreground ml-1 min-w-0 break-words">
                {sourceShort}
              </span>
            </div>
          </div>

          <p className="text-muted mt-1.5 line-clamp-2 text-xs leading-relaxed">
            {alert.description}
          </p>

          <div className="mt-3 sm:hidden">{dateTimeBlock}</div>
        </div>
      </Link>

      <div className="border-border hidden shrink-0 items-center gap-16 self-stretch px-3 py-2 sm:flex">
        <div className="shrink-0">{dateTimeBlock}</div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            className="cursor-pointer text-muted hover:text-foreground rounded-md p-1 transition-colors"
            aria-label="Bookmark alert"
            onClick={stopNavigation}
          >
            <Bookmark className="size-[20px]" strokeWidth={1.5} aria-hidden />
          </button>
          <button
            type="button"
            className="cursor-pointer text-muted hover:text-foreground rounded-md p-1 transition-colors"
            aria-label="More actions"
            onClick={stopNavigation}
          >
            <MoreVertical
              className="size-[20px]"
              strokeWidth={1.5}
              aria-hidden
            />
          </button>
        </div>
      </div>
    </div>
  );
};
