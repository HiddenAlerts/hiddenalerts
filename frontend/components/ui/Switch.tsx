'use client';

import { cn } from '@/lib/utils';
import * as React from 'react';

export type SwitchProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: React.ReactNode;
  id?: string;
  disabled?: boolean;
  className?: string;
};

/**
 * Accessible boolean toggle. Renders an optional label to the right, so
 * callers can pass rich content (e.g. a description line) as `label`.
 */
export function Switch({
  checked,
  onChange,
  label,
  id,
  disabled,
  className,
}: SwitchProps) {
  const uid = React.useId();
  const fieldId = id ?? `switch-${uid}`;

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <button
        type="button"
        role="switch"
        id={fieldId}
        aria-checked={checked}
        disabled={disabled}
        onClick={() => {
          if (disabled) return;
          onChange(!checked);
        }}
        className={cn(
          'focus-visible:ring-primary-500/30 relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus-visible:ring-2 focus-visible:outline-none',
          disabled
            ? 'cursor-not-allowed opacity-40'
            : 'cursor-pointer',
          checked ? 'bg-success' : 'bg-surface-muted',
        )}
      >
        <span
          className={cn(
            'inline-block size-4 transform rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-6' : 'translate-x-1',
          )}
        />
      </button>
      {label ? (
        <label
          htmlFor={fieldId}
          className={cn(
            'text-body text-sm',
            disabled ? 'cursor-not-allowed opacity-70' : 'cursor-pointer',
          )}
        >
          {label}
        </label>
      ) : null}
    </div>
  );
}
