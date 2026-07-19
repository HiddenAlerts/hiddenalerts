'use client';

import { alertDisplayedAtIso, scoreVisualTone } from '@/lib/alertDisplay';
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
import Link from 'next/link';
import type { FC } from 'react';

import { RiskBadge } from './RiskBadge';

const toneText: Record<ReturnType<typeof scoreVisualTone>, string> = {
  danger: 'text-danger',
  warning: 'text-warning',
  success: 'text-success',
  muted: 'text-body',
};

function cardAccentClass(riskBandLabel: string | null, riskLevelLabel: string) {
  if (riskBandLabel === 'CRITICAL') return 'border-l-danger border-l-[4px]';
  if (riskBandLabel === 'HIGH') return 'border-l-danger';
  if (riskLevelLabel === 'MEDIUM') return 'border-l-warning';
  if (riskLevelLabel === 'LOW') return 'border-l-success';
  return 'border-l-border';
}

function iconWellClass(riskBandLabel: string | null, riskLevelLabel: string) {
  if (riskBandLabel === 'CRITICAL') return 'bg-danger/20 text-danger';
  if (riskBandLabel === 'HIGH') return 'bg-danger-muted text-danger';
  if (riskLevelLabel === 'MEDIUM') return 'bg-warning-muted text-warning';
  if (riskLevelLabel === 'LOW') return 'bg-success-muted text-success';
  return 'bg-surface-muted text-body';
}

export type AlertRowProps = {
  alert: AlertItem;
  className?: string;
  /** Pass-through of `/alerts` query (`risk`, `page`) so detail “back” restores list state */
  alertsListReturnQuery?: string;
};

export const AlertRow: FC<AlertRowProps> = ({
  alert,
  className,
  alertsListReturnQuery,
}) => {
  const sourceShort = alert.sourceDisplayLabel ?? alert.sourceLabel;
  const categoryLine = formatDashboardAlertTypeLabel(alert.category);
  const tone = scoreVisualTone(
    alert.riskLevelLabel,
    alert.riskBand,
  );
  const scoreToneClass = toneText[tone];
  const displayedAtIso = alertDisplayedAtIso(alert);
  const dateLine = formatDashboardAlertDateOnlyUtc(displayedAtIso);
  const timeLine = formatDashboardAlertTimeUtcLine(displayedAtIso);

  const detailHref =
    alertsListReturnQuery != null && alertsListReturnQuery.length > 0
      ? `/alerts/${alert.id}?from=${encodeURIComponent(alertsListReturnQuery)}`
      : `/alerts/${alert.id}`;

  return (
    <Link
      href={detailHref}
      className={cn(
        'border-border bg-background-alt group focus-visible:ring-primary-500/40 flex w-full min-w-0 cursor-pointer flex-col justify-between gap-4 rounded-md border border-l-[3px] p-4 transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none sm:flex-row sm:items-center sm:gap-10',
        cardAccentClass(alert.riskBandLabel, alert.riskLevelLabel),
        'hover:bg-surface/20',
        className,
      )}
    >
      <div className="flex w-full min-w-0 flex-1 items-start gap-3 sm:max-w-[50%] sm:gap-4">
        <div
          className={cn(
            'flex size-11 shrink-0 items-center justify-center rounded-full sm:size-16',
            iconWellClass(alert.riskBandLabel, alert.riskLevelLabel),
          )}
        >
          <DashboardCategoryIcon
            category={alert.category}
            className="size-[22px] sm:size-7"
          />
        </div>

        <div className="min-w-0 flex-1">
          <h2 className="font-heading text-foreground line-clamp-1 text-base font-semibold tracking-tight sm:text-[1.2rem]">
            {alert.title}
          </h2>
          <p className="text-info mt-0.5 text-sm font-medium">{categoryLine}</p>
          <p className="text-muted mt-0.5 line-clamp-1 text-xs leading-relaxed sm:text-sm">
            {alert.description}
          </p>
          {alert.matchedEntity ? (
            <p className="text-muted mt-1 line-clamp-1 text-xs">
              Matched entity:{' '}
              <span className="text-body font-medium">
                {alert.matchedEntity}
              </span>
            </p>
          ) : null}
        </div>
      </div>

      <div className="flex w-full min-w-0 flex-wrap items-end justify-between gap-x-4 gap-y-3 sm:w-auto sm:shrink-0 sm:flex-nowrap sm:items-center sm:gap-6">
        <div className="flex items-end gap-6 sm:min-w-[5rem]">
          {alert.riskBandLabel ? (
            <RiskBadge label={alert.riskBandLabel} variant="outline" />
          ) : null}
          <p className="flex items-baseline gap-0.5 tabular-nums">
            {typeof alert.signalScore === 'number' ? (
              <>
                <span
                  className={cn(
                    'text-3xl leading-none font-bold sm:text-2xl',
                    scoreToneClass,
                  )}
                >
                  {alert.signalScore}
                </span>
                <span className="text-muted text-base leading-none font-medium sm:text-lg">
                  /100
                </span>
              </>
            ) : (
              <span className="text-muted text-2xl font-bold">—</span>
            )}
          </p>
        </div>

        <div
          aria-hidden
          className="bg-muted shrink-0 max-sm:my-0.5 max-sm:h-px max-sm:w-full max-sm:basis-full sm:h-10 sm:w-px"
        />

        <div className="flex min-w-0 gap-4 sm:gap-12">
          <div className="">
            <p className="text-muted text-xs font-medium">Source</p>
            <p className="text-foreground mt-0.5 line-clamp-2 text-sm font-medium">
              {sourceShort || '—'}
            </p>
          </div>
          <div>
            <p className="text-body text-muted text-sm tabular-nums">
              {dateLine}
            </p>
            <p className="text-muted mt-0.5 text-sm tabular-nums">{timeLine}</p>
          </div>
        </div>
      </div>
    </Link>
  );
};
