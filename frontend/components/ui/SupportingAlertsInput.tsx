'use client';

import { cn } from '@/lib/utils';
import { Plus, X } from 'lucide-react';
import * as React from 'react';

import { Button } from './button';
import { labelSize } from './input';

export type SupportingAlertValue = {
  url: string;
  title?: string;
};

export type SupportingAlertsInputProps = {
  label?: string;
  value: SupportingAlertValue[];
  onChange: (next: SupportingAlertValue[]) => void;
  id?: string;
  parentStyles?: string;
  disabled?: boolean;
};

/**
 * Numbered, editable list of supporting alert references (URL + optional
 * title per row) with add/remove controls — matches the API's
 * `supporting_alerts` shape.
 */
export function SupportingAlertsInput({
  label = 'Supporting Alerts',
  value,
  onChange,
  id,
  parentStyles,
  disabled,
}: SupportingAlertsInputProps) {
  const uid = React.useId();
  const fieldId = id ?? `supporting-alerts-${uid}`;

  function updateAt(index: number, next: Partial<SupportingAlertValue>) {
    onChange(value.map((v, i) => (i === index ? { ...v, ...next } : v)));
  }

  function removeAt(index: number) {
    onChange(value.filter((_, i) => i !== index));
  }

  function addRow() {
    onChange([...value, { url: '', title: '' }]);
  }

  return (
    <div className={cn('flex flex-col gap-2', parentStyles)}>
      {label ? (
        <label htmlFor={fieldId} className={labelSize.md}>
          {label}
        </label>
      ) : null}

      <div id={fieldId} className="flex flex-col gap-2">
        {value.map((alert, index) => (
          <div key={index} className="flex items-center gap-2">
            <span className="text-muted w-4 shrink-0 text-sm tabular-nums">
              {index + 1}
            </span>
            <input
              type="url"
              value={alert.url}
              disabled={disabled}
              onChange={e => updateAt(index, { url: e.target.value })}
              placeholder="https://example.com/article"
              className="font-manrope bg-surface text-body placeholder:text-muted border-border focus-visible:border-primary-500 focus-visible:ring-primary-500/30 h-10 w-full min-w-0 flex-[3] rounded-md border px-3 text-sm transition-colors focus:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-40"
            />
            <input
              type="text"
              value={alert.title ?? ''}
              disabled={disabled}
              onChange={e => updateAt(index, { title: e.target.value })}
              placeholder="Title (optional)"
              className="font-manrope bg-surface text-body placeholder:text-muted border-border focus-visible:border-primary-500 focus-visible:ring-primary-500/30 h-10 w-full min-w-0 flex-[2] rounded-md border px-3 text-sm transition-colors focus:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-40"
            />
            <button
              type="button"
              disabled={disabled}
              onClick={() => removeAt(index)}
              aria-label={`Remove supporting alert ${index + 1}`}
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
        onClick={addRow}
        leftIcon={<Plus className="size-4" aria-hidden />}
        className="self-start"
      >
        Add Supporting Alert
      </Button>
    </div>
  );
}
