'use client';

import { cn } from '@/lib/utils';
import * as React from 'react';

import { labelSize } from './input';

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  labelStyles?: string;
  parentStyles?: string;
  isError?: boolean;
  errorMessage?: string;
  addAsterisk?: boolean;
  /** Show a `value.length / maxLength` counter under the field. */
  showCounter?: boolean;
}

/**
 * Multi-line text input that mirrors the visual style of `Input`. Reuses the
 * same label sizing tokens for a consistent form look.
 */
const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
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
      showCounter,
      maxLength,
      value,
      defaultValue,
      ...props
    },
    ref,
  ) => {
    const uid = React.useId();
    const fieldId = id ?? (name !== undefined ? String(name) : `textarea-${uid}`);
    const showAsterisk = Boolean(
      required && addAsterisk && label && !label.includes('*'),
    );

    const [internalValue, setInternalValue] = React.useState(
      typeof defaultValue === 'string' ? defaultValue : '',
    );
    const currentValue =
      typeof value === 'string' ? value : internalValue;
    const counterText =
      showCounter && typeof maxLength === 'number'
        ? `${currentValue.length}/${maxLength}`
        : null;

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
          <textarea
            ref={ref}
            id={fieldId}
            name={name}
            disabled={disabled}
            required={required}
            maxLength={maxLength}
            value={value}
            defaultValue={defaultValue}
            onChange={e => {
              if (value === undefined) setInternalValue(e.target.value);
              props.onChange?.(e);
            }}
            className={cn(
              'font-manrope bg-surface text-body placeholder:text-muted w-full rounded-md border px-3 py-2.5 text-sm transition-colors',
              'min-h-[120px] resize-y',
              'focus:outline-none focus-visible:ring-2',
              isError
                ? 'border-danger focus-visible:border-danger focus-visible:ring-danger/25'
                : 'border-border focus-visible:border-primary-500 focus-visible:ring-primary-500/30',
              disabled && 'pointer-events-none opacity-40',
              counterText && 'pb-7',
              className,
            )}
            {...props}
          />
          {counterText ? (
            <span className="text-muted pointer-events-none absolute right-3 bottom-2 text-xs">
              {counterText}
            </span>
          ) : null}
        </div>

        {isError && errorMessage ? (
          <p className="text-danger-400 text-xs">{errorMessage}</p>
        ) : null}
      </div>
    );
  },
);

Textarea.displayName = 'Textarea';

export { Textarea };
