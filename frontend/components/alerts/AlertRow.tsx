'use client';

import Tag from '@/components/ui/Tag/Tag';
import { formatAlertDate } from '@/lib/formatAlertDate';
import { cn } from '@/lib/utils';
import type { AlertBadgeTone, AlertItem } from '@/types/alert';
import type { ComponentProps, FC } from 'react';
import { useState } from 'react';

type TagType = NonNullable<ComponentProps<typeof Tag>['type']>;

const sourceTagType: Record<AlertBadgeTone, TagType> = {
  danger: 'danger',
  success: 'success',
  info: 'info',
  warning: 'warning',
};

/** Heuristic: summaries longer than this usually exceed two lines at `text-sm`. */
const SUMMARY_TOGGLE_THRESHOLD = 120;

function riskMetaClass(label: string) {
  if (label === 'HIGH') return 'text-danger';
  if (label === 'MEDIUM') return 'text-warning';
  if (label === 'LOW') return 'text-success';
  return 'text-muted';
}

export type AlertRowProps = {
  alert: AlertItem;
  className?: string;
};

export const AlertRow: FC<AlertRowProps> = ({ alert, className }) => {
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  const sourceShort = alert.sourceDisplayLabel ?? alert.sourceLabel;
  const summary = alert.description;
  const showSummaryToggle = summary.trim().length > SUMMARY_TOGGLE_THRESHOLD;

  return (
    <tr
      className={cn(
        'border-border hover:bg-surface/60 border-b transition-colors last:border-b-0',
        className,
      )}
    >
      <td className="align-top px-4 py-4 lg:px-5">
        <div className="max-w-xl space-y-2">
          <p className="font-heading text-foreground text-base font-semibold leading-snug tracking-tight sm:text-lg">
            {alert.title}
          </p>
          <div className="space-y-1">
            <p
              className={cn(
                'text-body text-sm font-normal leading-relaxed',
                !summaryExpanded && showSummaryToggle && 'line-clamp-2',
              )}
            >
              {summary}
            </p>
            {showSummaryToggle ? (
              <button
                type="button"
                onClick={() => setSummaryExpanded(v => !v)}
                className="text-primary-400 hover:text-primary-300 cursor-pointer text-left text-xs font-medium underline-offset-2 hover:underline"
              >
                {summaryExpanded ? 'Show less' : 'Show more'}
              </button>
            ) : null}
          </div>
        </div>
      </td>
      <td className="align-top whitespace-nowrap px-4 py-4 lg:px-5">
        <div className="flex flex-col gap-2">
          <span
            className={cn(
              'text-xs font-semibold tracking-wide uppercase',
              riskMetaClass(alert.riskLevelLabel),
            )}
          >
            {alert.riskLevelLabel}
          </span>
          {typeof alert.signalScore === 'number' ? (
            <div className="space-y-0.5">
              <p className="text-muted text-[0.65rem] font-semibold tracking-wide uppercase">
                Signal score
              </p>
              <p className="text-foreground tabular-nums text-sm font-semibold leading-none">
                {alert.signalScore}
              </p>
            </div>
          ) : null}
        </div>
      </td>
      <td className="align-top px-4 py-4 lg:px-5">
        <div
          className="flex justify-center lg:justify-start"
          title={alert.sourceLabel}
        >
          <Tag
            title={sourceShort}
            type={sourceTagType[alert.badgeTone]}
            dot={false}
          />
        </div>
      </td>
      <td className="text-muted align-top whitespace-nowrap px-4 py-4 text-right text-sm lg:px-5">
        {formatAlertDate(alert.occurredAt)}
      </td>
    </tr>
  );
};
