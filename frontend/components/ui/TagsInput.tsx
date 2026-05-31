'use client';

import { cn } from '@/lib/utils';
import { X } from 'lucide-react';
import * as React from 'react';

import { labelSize } from './input';

export type TagsInputProps = {
  label?: string;
  /** Current list of tags. */
  value: string[];
  /** Called whenever the tag list changes. */
  onChange: (next: string[]) => void;
  placeholder?: string;
  id?: string;
  required?: boolean;
  addAsterisk?: boolean;
  isError?: boolean;
  errorMessage?: string;
  parentStyles?: string;
  className?: string;
  disabled?: boolean;
};

/**
 * Lightweight tag entry field: shows existing tags as removable chips and
 * lets the user type a new tag and press Enter (or comma) to add it.
 */
export function TagsInput({
  label,
  value,
  onChange,
  placeholder = 'Type and press Enter…',
  id,
  required,
  addAsterisk,
  isError,
  errorMessage,
  parentStyles,
  className,
  disabled,
}: TagsInputProps) {
  const uid = React.useId();
  const fieldId = id ?? `tags-${uid}`;
  const [draft, setDraft] = React.useState('');

  const showAsterisk = Boolean(
    required && addAsterisk && label && !label.includes('*'),
  );

  function commit(raw: string) {
    const tag = raw.trim();
    if (!tag) return;
    if (value.includes(tag)) {
      setDraft('');
      return;
    }
    onChange([...value, tag]);
    setDraft('');
  }

  function remove(tag: string) {
    onChange(value.filter(t => t !== tag));
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      commit(draft);
    } else if (e.key === 'Backspace' && draft === '' && value.length > 0) {
      remove(value[value.length - 1]);
    }
  }

  return (
    <div
      className={cn(
        'flex flex-col gap-2',
        disabled && 'cursor-not-allowed',
        parentStyles,
      )}
    >
      {label ? (
        <label htmlFor={fieldId} className={labelSize.md}>
          {label}
          {showAsterisk ? (
            <span className="text-danger-500 ml-0.5 font-medium">*</span>
          ) : null}
        </label>
      ) : null}

      <div
        className={cn(
          'font-manrope bg-surface flex min-h-11 flex-wrap items-center gap-1.5 rounded-md border px-2 py-1.5 transition-colors',
          'focus-within:ring-2',
          isError
            ? 'border-danger focus-within:border-danger focus-within:ring-danger/25'
            : 'border-border focus-within:border-primary-500 focus-within:ring-primary-500/30',
          disabled && 'pointer-events-none opacity-40',
          className,
        )}
      >
        {value.map(tag => (
          <span
            key={tag}
            className="bg-surface-muted text-body inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs"
          >
            <span>{tag}</span>
            <button
              type="button"
              onClick={() => remove(tag)}
              className="text-muted hover:text-foreground inline-flex cursor-pointer items-center justify-center"
              aria-label={`Remove ${tag}`}
            >
              <X className="size-3" aria-hidden />
            </button>
          </span>
        ))}

        <input
          id={fieldId}
          type="text"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => commit(draft)}
          placeholder={value.length === 0 ? placeholder : ''}
          className="text-body placeholder:text-muted min-w-[120px] flex-1 bg-transparent px-1 py-1 text-sm focus:outline-none"
          disabled={disabled}
        />
      </div>

      {isError && errorMessage ? (
        <p className="text-danger-400 text-xs">{errorMessage}</p>
      ) : null}
    </div>
  );
}
