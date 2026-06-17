'use client';

import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import * as React from 'react';

import { labelSize } from './input';

export type SelectOption = {
  value: string;
  label: string;
};

export interface SelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  label?: string;
  labelStyles?: string;
  parentStyles?: string;
  isError?: boolean;
  errorMessage?: string;
  addAsterisk?: boolean;
  options: ReadonlyArray<SelectOption>;
  /** Optional placeholder rendered when value is empty. */
  placeholder?: string;
  /** Custom class for the visible value text (e.g. red text for "High"). */
  valueClassName?: string;
}

/**
 * Native `<select>` styled to match `Input`. Uses the same label tokens for
 * consistent form layouts.
 */
const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      className,
      name,
      id,
      label,
      labelStyles,
      parentStyles,
      isError,
      errorMessage,
      addAsterisk,
      required,
      disabled,
      options,
      placeholder,
      valueClassName,
      ...props
    },
    ref,
  ) => {
    const uid = React.useId();
    const fieldId = id ?? (name !== undefined ? String(name) : `select-${uid}`);
    const showAsterisk = Boolean(
      required && addAsterisk && label && !label.includes('*'),
    );

    return (
      <div
        className={cn(
          'flex flex-col gap-2',
          disabled && 'cursor-not-allowed',
          parentStyles,
        )}
      >
        {label ? (
          <label htmlFor={fieldId} className={cn(labelSize.md, labelStyles)}>
            {label}
            {showAsterisk ? (
              <span className="text-danger-500 ml-0.5 font-medium">*</span>
            ) : null}
          </label>
        ) : null}

        <div className="relative">
          <select
            ref={ref}
            id={fieldId}
            name={name}
            disabled={disabled}
            required={required}
            className={cn(
              'font-manrope bg-surface text-body w-full cursor-pointer appearance-none rounded-md border pr-10 pl-3 text-sm transition-colors',
              'h-11',
              'focus:outline-none focus-visible:ring-2',
              isError
                ? 'border-danger focus-visible:border-danger focus-visible:ring-danger/25'
                : 'border-border hover:border-primary-500/50 focus-visible:border-primary-500 focus-visible:ring-primary-500/30',
              disabled && 'pointer-events-none opacity-40',
              valueClassName,
              className,
            )}
            {...props}
          >
            {placeholder ? (
              <option value="" disabled hidden>
                {placeholder}
              </option>
            ) : null}
            {options.map(opt => (
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

        {isError && errorMessage ? (
          <p className="text-danger-400 text-xs">{errorMessage}</p>
        ) : null}
      </div>
    );
  },
);

Select.displayName = 'Select';

export { Select };
