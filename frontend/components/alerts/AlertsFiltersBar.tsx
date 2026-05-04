'use client';

import {
  ALERTS_RISK_FILTER_OPTIONS,
  type AlertsRiskFilterValue,
} from '@/data/alertRiskFilterOptions';
import { API_ALERT_CATEGORY_OPTIONS } from '@/data/apiAlertCategories';
import { cn } from '@/lib/utils';
import type { FC } from 'react';

import { FilterDropdown } from './FilterDropdown';

export type AlertsFiltersBarProps = {
  riskFilter: AlertsRiskFilterValue;
  categoryFilter: string;
  onRiskChange: (risk: AlertsRiskFilterValue) => void;
  onCategoryChange: (category: string) => void;
  className?: string;
};

function riskButtonClass(
  value: string,
  selected: boolean,
): string {
  const base =
    'cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium transition-colors';
  if (!selected) {
    return cn(
      base,
      'border-border bg-surface text-muted hover:bg-surface-muted hover:text-body',
    );
  }
  if (value === 'high') {
    return cn(base, 'border-danger bg-transparent text-danger');
  }
  if (value === 'medium') {
    return cn(base, 'border-warning bg-transparent text-warning');
  }
  if (value === 'low') {
    return cn(base, 'border-success bg-transparent text-success');
  }
  return cn(base, 'border-border text-foreground bg-transparent');
}

export const AlertsFiltersBar: FC<AlertsFiltersBarProps> = ({
  riskFilter,
  categoryFilter,
  onRiskChange,
  onCategoryChange,
  className,
}) => (
  <div
    className={cn(
      'border-border bg-surface/30 flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between',
      className,
    )}
  >
    <div className="flex flex-wrap items-center gap-2">
      {ALERTS_RISK_FILTER_OPTIONS.map(opt => {
        const selected = riskFilter === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onRiskChange(opt.value)}
            className={riskButtonClass(opt.value, selected)}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
    <div className="flex min-w-0 flex-col gap-1.5 sm:max-w-[min(100%,18rem)] sm:flex-none">
      <span className="text-muted text-xs font-medium">Filter by Type</span>
      <FilterDropdown
        id="alerts-category-filter"
        label="Filter by Type"
        value={categoryFilter}
        options={API_ALERT_CATEGORY_OPTIONS}
        onChange={onCategoryChange}
        className="min-w-0 sm:min-w-[14rem]"
      />
    </div>
  </div>
);
