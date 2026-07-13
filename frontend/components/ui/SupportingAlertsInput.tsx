'use client';

import { cn } from '@/lib/utils';
import { Plus, X } from 'lucide-react';
import * as React from 'react';

import { Button } from './button';
import { labelSize } from './input';

export type SupportingAlertValue = {
  /** Maps to API `supporting_alerts[].url`. */
  url: string;
  /** Maps to API `supporting_alerts[].title` — shown as Source Name in the CMS. */
  title?: string;
};

export type SupportingAlertsInputProps = {
  label?: string;
  description?: string;
  value: SupportingAlertValue[];
  onChange: (next: SupportingAlertValue[]) => void;
  id?: string;
  parentStyles?: string;
  disabled?: boolean;
};

/**
 * Editable list of external supporting sources (Name + URL).
 * Persists as API `supporting_alerts` where `title` = Source Name.
 */
export function SupportingAlertsInput({
  label = 'Supporting Sources',
  description = 'External references used to prepare this brief (for example FBI, DOJ, FinCEN, SEC, CISA). Source count on the subscriber page is calculated from this list.',
  value,
  onChange,
  id,
  parentStyles,
  disabled,
}: SupportingAlertsInputProps) {
  const uid = React.useId();
  const fieldId = id ?? `supporting-sources-${uid}`;

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

      {description ? (
        <p className="text-muted -mt-0.5 text-xs leading-relaxed">{description}</p>
      ) : null}

      <div id={fieldId} className="flex flex-col gap-3">
        {value.map((source, index) => (
          <div
            key={index}
            className="border-border bg-surface/30 flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-end"
          >
            <span className="text-muted w-4 shrink-0 text-sm tabular-nums sm:pb-2.5">
              {index + 1}
            </span>

            <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-2">
              <div className="flex min-w-0 flex-col gap-1">
                <span className="text-muted text-xs font-medium">Source Name</span>
                <input
                  type="text"
                  value={source.title ?? ''}
                  disabled={disabled}
                  onChange={e => updateAt(index, { title: e.target.value })}
                  placeholder="e.g. FBI, FinCEN, KrebsOnSecurity"
                  aria-label={`Source name ${index + 1}`}
                  className="font-manrope bg-surface text-body placeholder:text-muted border-border focus-visible:border-primary-500 focus-visible:ring-primary-500/30 h-10 w-full rounded-md border px-3 text-sm transition-colors focus:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-40"
                />
              </div>
              <div className="flex min-w-0 flex-col gap-1">
                <span className="text-muted text-xs font-medium">URL</span>
                <input
                  type="url"
                  value={source.url}
                  disabled={disabled}
                  onChange={e => updateAt(index, { url: e.target.value })}
                  placeholder="https://…"
                  aria-label={`Source URL ${index + 1}`}
                  className="font-manrope bg-surface text-body placeholder:text-muted border-border focus-visible:border-primary-500 focus-visible:ring-primary-500/30 h-10 w-full rounded-md border px-3 text-sm transition-colors focus:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-40"
                />
              </div>
            </div>

            <button
              type="button"
              disabled={disabled}
              onClick={() => removeAt(index)}
              aria-label={`Remove source ${index + 1}`}
              className="text-muted hover:text-danger inline-flex size-8 shrink-0 items-center justify-center self-end disabled:pointer-events-none disabled:opacity-40 sm:mb-1"
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
        Add Supporting Source
      </Button>
    </div>
  );
}
