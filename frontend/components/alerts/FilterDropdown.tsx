'use client';

import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import type { FC } from 'react';

export type FilterOption = { value: string; label: string };

export type FilterDropdownProps = {
  id: string;
  label: string;
  value: string;
  options: readonly FilterOption[];
  onChange: (value: string) => void;
  className?: string;
};

export const FilterDropdown: FC<FilterDropdownProps> = ({
  id,
  label,
  value,
  options,
  onChange,
  className,
}) => (
  <div className={cn('relative min-w-[140px]', className)}>
    <label htmlFor={id} className="sr-only">
      {label}
    </label>
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        'border-border bg-surface text-body hover:border-primary-500/50',
        'focus-visible:ring-primary-500/40 h-10 w-full cursor-pointer appearance-none rounded-md border',
        'px-3 pr-9 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none',
      )}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
    <ChevronDown
      className="text-muted pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2"
      aria-hidden
    />
  </div>
);
