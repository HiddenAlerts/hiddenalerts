'use client';

import { FilterDropdown } from '@/components/alerts/FilterDropdown';
import {
  BRIEF_RISK_FILTER_OPTIONS,
  BRIEF_SORT_OPTIONS,
} from '@/data/subscriberBriefs';
import { cn } from '@/lib/utils';
import type {
  BriefFilters,
  BriefRiskFilterValue,
  BriefSortValue,
} from '@/types/briefs';
import {
  Calendar,
  Lock,
  RotateCcw,
  Search,
  ShieldAlert,
  Tag,
} from 'lucide-react';
import type { FC } from 'react';

export type BriefsLibraryHeaderProps = {
  filters: BriefFilters;
  categoryOptions: ReadonlyArray<{ value: string; label: string }>;
  onSearchChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onRiskChange: (value: BriefRiskFilterValue) => void;
  onSortChange: (value: BriefSortValue) => void;
  onReset: () => void;
  hasActiveFilters: boolean;
  className?: string;
};

export const BriefsLibraryHeader: FC<BriefsLibraryHeaderProps> = ({
  filters,
  categoryOptions,
  onSearchChange,
  onCategoryChange,
  onRiskChange,
  onSortChange,
  onReset,
  hasActiveFilters,
  className,
}) => (
  <header className={cn('space-y-5', className)}>
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0 space-y-2">
        <h1 className="font-heading text-foreground inline-flex items-center gap-2 text-2xl font-bold tracking-tight sm:text-3xl">
          Intelligence Brief Library
        </h1>
        <p className="text-danger text-sm font-semibold tracking-wide">
          Signals Before the Headlines
        </p>
        <p className="text-muted max-w-2xl text-sm leading-relaxed">
          Access curated intelligence briefs identifying emerging trends,
          criminal methodologies, cyber threats, national security risks, and
          hidden signals before they become mainstream headlines.
        </p>
      </div>

      <div className="w-full max-w-md shrink-0 lg:w-[26rem]">
        <label htmlFor="brief-search" className="sr-only">
          Search intelligence briefs
        </label>
        <div className="relative">
          <Search
            className="text-muted pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
            aria-hidden
          />
          <input
            id="brief-search"
            type="search"
            value={filters.search}
            onChange={event => onSearchChange(event.target.value)}
            placeholder="Search intelligence briefs..."
            className="border-border bg-surface text-body placeholder:text-muted focus-visible:ring-primary-500/40 hover:border-primary-500/50 h-11 w-full rounded-lg border pr-3 pl-10 text-sm transition-colors focus-visible:ring-2 focus-visible:outline-none"
          />
        </div>
      </div>
    </div>

    <div className="border-border bg-surface/25 flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:flex-wrap sm:items-center">
      <FilterDropdown
        id="brief-category-filter"
        label="Filter by category"
        value={filters.category}
        options={categoryOptions}
        onChange={onCategoryChange}
        leftIcon={<Tag aria-hidden />}
        className="w-full sm:w-auto sm:min-w-[12rem]"
      />
      <FilterDropdown
        id="brief-risk-filter"
        label="Filter by risk level"
        value={filters.risk}
        options={BRIEF_RISK_FILTER_OPTIONS}
        onChange={value => onRiskChange(value as BriefRiskFilterValue)}
        leftIcon={<ShieldAlert aria-hidden />}
        className="w-full sm:w-auto sm:min-w-[11rem]"
      />
      <FilterDropdown
        id="brief-sort"
        label="Sort briefs"
        value={filters.sort}
        options={BRIEF_SORT_OPTIONS}
        onChange={value => onSortChange(value as BriefSortValue)}
        leftIcon={<Calendar aria-hidden />}
        className="w-full sm:w-auto sm:min-w-[11rem]"
      />

      <button
        type="button"
        onClick={onReset}
        disabled={!hasActiveFilters}
        className="border-border text-body hover:border-primary-500/50 hover:text-foreground focus-visible:ring-primary-500/40 inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-sm border px-4 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-40 sm:ml-auto"
      >
        <RotateCcw className="size-4" aria-hidden />
        Reset Filters
      </button>
    </div>
  </header>
);
