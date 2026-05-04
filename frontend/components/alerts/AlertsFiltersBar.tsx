'use client';

import { RiskCountPill } from '@/components/ui/RiskCountPill';
import {
  ALERTS_RISK_FILTER_OPTIONS,
  type AlertsRiskFilterValue,
} from '@/data/alertRiskFilterOptions';
import { API_ALERT_CATEGORY_OPTIONS } from '@/data/apiAlertCategories';
import { cn } from '@/lib/utils';
import { Filter } from 'lucide-react';
import type { FC } from 'react';

import { FilterDropdown } from './FilterDropdown';

export type AlertsFiltersBarProps = {
  riskFilter: AlertsRiskFilterValue;
  categoryFilter: string;
  /** From `GET /alerts/stats` (via `mapAlertsStatsToRiskCounts`). Omitted values show “—”. */
  riskCounts?: Partial<Record<AlertsRiskFilterValue, number>>;
  onRiskChange: (risk: AlertsRiskFilterValue) => void;
  onCategoryChange: (category: string) => void;
  className?: string;
};

function segmentLabelTone(
  value: AlertsRiskFilterValue,
  selected: boolean,
): string {
  if (selected) {
    if (value === 'high') return 'text-danger';
    if (value === 'medium') return 'text-warning';
    if (value === 'low') return 'text-success';
    return 'text-foreground';
  }
  if (value === 'high') return 'text-danger/90';
  if (value === 'medium') return 'text-warning/90';
  if (value === 'low') return 'text-success/90';
  return 'text-body';
}

function segmentSurface(
  selected: boolean,
  value: AlertsRiskFilterValue,
): string {
  if (!selected) return 'bg-transparent';
  if (value === 'high') return 'bg-danger/15 ring-1 ring-inset ring-danger';
  if (value === 'medium') return 'bg-warning/15 ring-1 ring-inset ring-warning';
  if (value === 'low') return 'bg-success/15 ring-1 ring-inset ring-success';
  return 'bg-surface-muted/90 ring-1 ring-inset ring-border';
}

export const AlertsFiltersBar: FC<AlertsFiltersBarProps> = ({
  riskFilter,
  categoryFilter,
  riskCounts,
  onRiskChange,
  onCategoryChange,
  className,
}) => (
  <div
    className={cn(
      'border-border bg-surface/25 flex flex-col gap-4 overflow-hidden rounded-sm border px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:px-4 sm:py-3',
      className,
    )}
  >
    <div
      className="border-border bg-background-alt/60 flex w-full min-w-0 overflow-x-auto rounded-sm border sm:w-auto sm:flex-1 sm:justify-start lg:max-w-max"
      role="group"
      aria-label="Filter by risk level"
    >
      {ALERTS_RISK_FILTER_OPTIONS.map((opt, index) => {
        const selected = riskFilter === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onRiskChange(opt.value)}
            aria-pressed={selected}
            className={cn(
              'flex min-h-[44px] min-w-0 flex-1 cursor-pointer items-center justify-center gap-2 rounded-sm px-3 py-2.5 text-sm font-medium whitespace-nowrap transition-colors sm:min-h-0 sm:flex-none sm:px-5',
              'focus-visible:ring-primary-500/50 focus-visible:ring-offset-background focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none',
              index > 0 && 'border-border border-l',
              segmentSurface(selected, opt.value),
              segmentLabelTone(opt.value, selected),
            )}
          >
            <span>{opt.label}</span>
            <RiskCountPill
              variant={opt.value}
              count={riskCounts?.[opt.value]}
            />
          </button>
        );
      })}
    </div>

    <div className="flex min-w-0 shrink-0 flex-col gap-1.5 sm:w-[min(100%,18rem)]">
      <FilterDropdown
        id="alerts-category-filter"
        label="Filter by Type"
        value={categoryFilter}
        options={API_ALERT_CATEGORY_OPTIONS}
        onChange={onCategoryChange}
        leftIcon={<Filter aria-hidden />}
        className="min-w-0"
      />
    </div>
  </div>
);
