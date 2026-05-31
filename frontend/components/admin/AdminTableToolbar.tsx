'use client';

import { Input } from '@/components';
import { cn } from '@/lib/utils';
import { ChevronDown, Search } from 'lucide-react';
import type { FC } from 'react';

export type AdminToolbarFilterOption = {
  value: string;
  label: string;
};

export type AdminToolbarFilter = {
  id: string;
  value: string;
  options: readonly AdminToolbarFilterOption[];
  onChange: (value: string) => void;
  ariaLabel?: string;
};

export type AdminTableToolbarProps = {
  searchValue: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  filters?: AdminToolbarFilter[];
  className?: string;
};

const selectClass =
  'border-border bg-surface text-body hover:border-primary-500/50 focus-visible:ring-primary-500/40 h-11 cursor-pointer appearance-none rounded-md border pr-9 pl-3 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none';

/**
 * Toolbar above admin tables: a single search field plus 0-N dropdown filters.
 */
export const AdminTableToolbar: FC<AdminTableToolbarProps> = ({
  searchValue,
  onSearchChange,
  searchPlaceholder = 'Search…',
  filters = [],
  className,
}) => (
  <div
    className={cn(
      'flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center',
      className,
    )}
  >
    <div className="min-w-0 flex-1 sm:max-w-md">
      <Input
        type="search"
        value={searchValue}
        onChange={e => onSearchChange(e.target.value)}
        placeholder={searchPlaceholder}
        aria-label={searchPlaceholder}
        leftIcon={<Search aria-hidden />}
      />
    </div>

    {filters.map(filter => (
      <div key={filter.id} className="relative w-full sm:w-44">
        <label htmlFor={filter.id} className="sr-only">
          {filter.ariaLabel ?? filter.id}
        </label>
        <select
          id={filter.id}
          value={filter.value}
          onChange={e => filter.onChange(e.target.value)}
          className={cn(selectClass, 'w-full')}
        >
          {filter.options.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown
          className="text-muted pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2"
          aria-hidden
        />
      </div>
    ))}
  </div>
);
