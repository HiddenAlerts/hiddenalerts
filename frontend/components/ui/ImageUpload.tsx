'use client';

import { cn } from '@/lib/utils';
import { ImageIcon, Trash2 } from 'lucide-react';
import * as React from 'react';

import { labelSize } from './input';

export type ImageUploadProps = {
  label?: string;
  /** Preview URL for the currently selected image, if any. */
  value?: string;
  /** Called with a local object URL when a new file is chosen. */
  onChange: (url: string | undefined) => void;
  hint?: string;
  id?: string;
  parentStyles?: string;
  disabled?: boolean;
};

/**
 * Featured image picker: shows a preview with "Change Image"/remove
 * controls. Selecting a file only creates a local object URL preview —
 * there is no upload backend wired up yet.
 */
export function ImageUpload({
  label = 'Featured Image',
  value,
  onChange,
  hint = 'Recommended size: 1200x675px',
  id,
  parentStyles,
  disabled,
}: ImageUploadProps) {
  const uid = React.useId();
  const fieldId = id ?? `image-upload-${uid}`;
  const inputRef = React.useRef<HTMLInputElement>(null);
  const objectUrlRef = React.useRef<string | undefined>(undefined);

  React.useEffect(
    () => () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    },
    [],
  );

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    const url = URL.createObjectURL(file);
    objectUrlRef.current = url;
    onChange(url);
  }

  function handleRemove() {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = undefined;
    onChange(undefined);
  }

  return (
    <div className={cn('flex flex-col gap-2', parentStyles)}>
      {label ? (
        <label htmlFor={fieldId} className={labelSize.md}>
          {label}
        </label>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div
          className={cn(
            'border-border bg-surface flex aspect-video w-full items-center justify-center overflow-hidden rounded-md border sm:w-64',
          )}
        >
          {value ? (
            // Local preview only (object URL / data URL); no remote host to optimize via next/image.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={value}
              alt="Featured image preview"
              className="size-full object-cover"
            />
          ) : (
            <ImageIcon className="text-muted size-8" aria-hidden />
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
            className="border-border bg-surface text-body hover:bg-surface-muted inline-flex h-9 items-center rounded-md border px-4 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-40"
          >
            Change Image
          </button>
          {value ? (
            <button
              type="button"
              disabled={disabled}
              onClick={handleRemove}
              aria-label="Remove featured image"
              className="border-border bg-surface text-muted hover:text-danger hover:border-danger/40 inline-flex size-9 items-center justify-center rounded-md border transition-colors disabled:pointer-events-none disabled:opacity-40"
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          ) : null}
        </div>
      </div>

      {hint ? <p className="text-muted text-xs">{hint}</p> : null}

      <input
        ref={inputRef}
        id={fieldId}
        type="file"
        accept="image/*"
        disabled={disabled}
        onChange={handleFileChange}
        className="hidden"
      />
    </div>
  );
}
