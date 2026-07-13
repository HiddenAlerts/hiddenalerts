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
  /** Trimmed search query from URL — shows a clear control when set. */
  activeSearchQuery?: string | null;
  onClearSearch?: () => void;
  className?: string;
};

function segmentLabelTone(
  value: AlertsRiskFilterValue,
  selected: boolean,
): string {
  if (selected) {
    if (value === 'critical') return 'text-danger';
    if (value === 'high') return 'text-warning';
    return 'text-foreground';
  }
  if (value === 'critical') return 'text-danger/90';
  if (value === 'high') return 'text-warning/90';
  return 'text-body';
}

function segmentSurface(
  selected: boolean,
  value: AlertsRiskFilterValue,
): string {
  if (!selected) return 'bg-transparent';
  if (value === 'critical') return 'bg-danger/15 ring-1 ring-inset ring-danger';
  if (value === 'high') return 'bg-warning/15 ring-1 ring-inset ring-warning';
  return 'bg-surface-muted/90 ring-1 ring-inset ring-border';
}

export const AlertsFiltersBar: FC<AlertsFiltersBarProps> = ({
  riskFilter,
  categoryFilter,
  riskCounts,
  onRiskChange,
  onCategoryChange,
  activeSearchQuery,
  onClearSearch,
  className,
}) => {
  const searchTrim =
    typeof activeSearchQuery === 'string' ? activeSearchQuery.trim() : '';
  const showClearSearch =
    searchTrim.length > 0 && typeof onClearSearch === 'function';

  return (
    <div
      className={cn(
        'border-border bg-surface/25 flex flex-col gap-4 overflow-hidden rounded-sm border px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:px-4 sm:py-3',
        className,
      )}
    >
      <div
        className={cn(
          'grid w-full grid-cols-3 gap-2 sm:flex sm:w-auto sm:min-w-0 sm:flex-1 sm:gap-0 sm:overflow-x-auto sm:rounded-sm sm:border sm:border-border sm:bg-background-alt/60 sm:justify-start lg:max-w-max',
        )}
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
                'border-border bg-background-alt/50 flex min-h-[44px] w-full cursor-pointer flex-row items-center justify-center gap-2 rounded-md border px-3 py-2.5 text-sm font-medium whitespace-nowrap transition-colors sm:min-h-0 sm:w-auto sm:min-w-0 sm:flex-none sm:rounded-none sm:border-0 sm:bg-transparent sm:px-5',
                'focus-visible:ring-primary-500/50 focus-visible:ring-offset-background focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none',
                index > 0 && 'sm:border-border sm:border-l',
                segmentSurface(selected, opt.value),
                segmentLabelTone(opt.value, selected),
              )}
            >
              <span className="shrink-0">{opt.label}</span>
              <RiskCountPill
                variant={opt.value}
                count={riskCounts?.[opt.value]}
                className="shrink-0"
              />
            </button>
          );
        })}
      </div>

      <div className="flex min-w-0 shrink-0 flex-col gap-2 sm:w-[min(100%,18rem)] sm:items-end">
        <FilterDropdown
          id="alerts-category-filter"
          label="Filter by Type"
          value={categoryFilter}
          options={API_ALERT_CATEGORY_OPTIONS}
          onChange={onCategoryChange}
          leftIcon={<Filter aria-hidden />}
          className="min-w-0 w-full"
        />
        {showClearSearch ? (
          <button
            type="button"
            onClick={onClearSearch}
            className="text-muted hover:text-foreground focus-visible:ring-primary-500/50 text-xs font-medium underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none sm:text-right"
          >
            Clear search
          </button>
        ) : null}
      </div>
    </div>
  );
};
