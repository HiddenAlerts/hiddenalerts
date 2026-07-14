'use client';

import { cn } from '@/lib/utils';
import { ImageIcon, Trash2 } from 'lucide-react';
import * as React from 'react';

import { labelSize } from './input';

export type ImageUploadProps = {
  label?: string;
  /** Preview URL for the currently selected image, if any (server URL or local preview). */
  value?: string;
  /** Called with the raw file the user picked — the parent owns upload/preview. */
  onFileSelect: (file: File) => void;
  /** Called when the user removes the current image. */
  onRemove: () => void;
  hint?: string;
  id?: string;
  parentStyles?: string;
  disabled?: boolean;
};

/**
 * Featured image picker: shows a preview with "Change Image"/remove
 * controls. Purely controlled — the parent decides what `value` to show and
 * what happens with the selected `File`/removal (e.g. uploading it, or just
 * previewing until the brief is saved).
 */
export function ImageUpload({
  label = 'Featured Image',
  value,
  onFileSelect,
  onRemove,
  hint = 'Recommended size: 1200×675px (16:9)',
  id,
  parentStyles,
  disabled,
}: ImageUploadProps) {
  const uid = React.useId();
  const fieldId = id ?? `image-upload-${uid}`;
  const inputRef = React.useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (file) onFileSelect(file);
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
            // Local preview or server-hosted URL; no fixed remote host to optimize via next/image.
            // object-contain: tall CMS covers (infographics) must stay fully visible —
            // object-cover zooms into dark centers and looks like a missing image.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={value}
              alt="Featured image preview"
              className="size-full object-contain"
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
              onClick={onRemove}
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
