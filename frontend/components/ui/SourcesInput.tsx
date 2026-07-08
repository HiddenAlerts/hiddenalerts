'use client';

import { cn } from '@/lib/utils';
import { Plus, X } from 'lucide-react';
import * as React from 'react';

import { Button } from './button';
import { labelSize } from './input';

export type SourcesInputProps = {
  label?: string;
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  id?: string;
  parentStyles?: string;
  disabled?: boolean;
};

/**
 * Numbered, editable list of source citations with add/remove controls.
 */
export function SourcesInput({
  label = 'Sources',
  value,
  onChange,
  placeholder = 'e.g. Public Report – Source Name – Title',
  id,
  parentStyles,
  disabled,
}: SourcesInputProps) {
  const uid = React.useId();
  const fieldId = id ?? `sources-${uid}`;

  function updateAt(index: number, text: string) {
    onChange(value.map((v, i) => (i === index ? text : v)));
  }

  function removeAt(index: number) {
    onChange(value.filter((_, i) => i !== index));
  }

  function addSource() {
    onChange([...value, '']);
  }

  return (
    <div className={cn('flex flex-col gap-2', parentStyles)}>
      {label ? (
        <label htmlFor={fieldId} className={labelSize.md}>
          {label}
        </label>
      ) : null}

      <div id={fieldId} className="flex flex-col gap-2">
        {value.map((source, index) => (
          <div key={index} className="flex items-center gap-2">
            <span className="text-muted w-4 shrink-0 text-sm tabular-nums">
              {index + 1}
            </span>
            <input
              type="text"
              value={source}
              disabled={disabled}
              onChange={e => updateAt(index, e.target.value)}
              placeholder={placeholder}
              className="font-manrope bg-surface text-body placeholder:text-muted border-border focus-visible:border-primary-500 focus-visible:ring-primary-500/30 h-10 w-full min-w-0 rounded-md border px-3 text-sm transition-colors focus:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-40"
            />
            <button
              type="button"
              disabled={disabled}
              onClick={() => removeAt(index)}
              aria-label={`Remove source ${index + 1}`}
              className="text-muted hover:text-danger inline-flex size-8 shrink-0 items-center justify-center disabled:pointer-events-none disabled:opacity-40"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={addSource}
        leftIcon={<Plus className="size-4" aria-hidden />}
        className="self-start"
      >
        Add Source
      </Button>
    </div>
  );
}
