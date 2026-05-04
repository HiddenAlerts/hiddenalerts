'use client';

import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import type { FC, ReactNode } from 'react';

export type FilterOption = { value: string; label: string };

export type FilterDropdownProps = {
  id: string;
  label: string;
  value: string;
  options: readonly FilterOption[];
  onChange: (value: string) => void;
  className?: string;
  /** Renders inside the field on the left (e.g. filter funnel icon). */
  leftIcon?: ReactNode;
};

export const FilterDropdown: FC<FilterDropdownProps> = ({
  id,
  label,
  value,
  options,
  onChange,
  className,
  leftIcon,
}) => (
  <div className={cn('relative min-w-[140px]', className)}>
    <label htmlFor={id} className="sr-only">
      {label}
    </label>
    {leftIcon ? (
      <span
        className="text-muted pointer-events-none absolute top-1/2 left-3 z-10 flex size-4 -translate-y-1/2 items-center justify-center [&_svg]:size-4"
        aria-hidden
      >
        {leftIcon}
      </span>
    ) : null}
    <select
      id={id}
      value={value}
      onChange={e => onChange(e.target.value)}
      className={cn(
        'border-border bg-surface text-body hover:border-primary-500/50',
        'focus-visible:ring-primary-500/40 h-10 w-full cursor-pointer appearance-none rounded-sm border',
        'pr-9 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none',
        leftIcon ? 'pl-10' : 'px-3',
      )}
    >
      {options.map(opt => (
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
