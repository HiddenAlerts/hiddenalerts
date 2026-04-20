'use client';

import {
  ALERT_CATEGORY_OPTIONS,
  ALERT_SORT_OPTIONS,
  MOCK_ALERTS,
} from '@/data/mockAlerts';
import { useAlertsList } from '@/hooks/useAlertsList';
import { cn } from '@/lib/utils';
import type { FC } from 'react';

import { AlertTable } from './AlertTable';
import { FilterDropdown } from './FilterDropdown';
import { Pagination } from './Pagination';

export const AlertsScreen: FC = () => {
  const list = useAlertsList({ items: MOCK_ALERTS, pageSize: 5 });

  const categoryOptions = [...ALERT_CATEGORY_OPTIONS];
  const sortOptions = [...ALERT_SORT_OPTIONS];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight">
            Alerts
          </h1>
          <p className="text-muted mt-1 text-sm">
            Review intelligence signals and system activity.
          </p>
        </div>

        {/* <div className="flex flex-wrap gap-2 sm:justify-end">
          <FilterDropdown
            id="alert-category"
            label="Category"
            value={list.category}
            options={categoryOptions}
            onChange={list.setCategory}
          />
          <FilterDropdown
            id="alert-sort"
            label="Sort"
            value={list.sort}
            options={sortOptions}
            onChange={(v) => list.setSort(v as 'recent' | 'oldest')}
          />
        </div> */}
      </div>

      <div className="space-y-2">
        <p className="text-muted text-xs font-medium tracking-wide uppercase">
          Category
        </p>
        <div className="flex flex-wrap gap-2">
          {ALERT_CATEGORY_OPTIONS.map(opt => {
            const selected = list.category === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => list.setCategory(opt.value)}
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                  selected
                    ? 'bg-primary-500 text-white'
                    : 'bg-surface text-body hover:bg-surface-muted border border-transparent',
                )}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      <AlertTable alerts={list.pageItems} />

      {list.totalCount > 0 ? (
        <Pagination
          page={list.page}
          totalPages={list.totalPages}
          onPageChange={list.setPage}
        />
      ) : null}
    </div>
  );
};
