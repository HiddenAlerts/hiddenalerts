'use client';

import { cn } from '@/lib/utils';
import { useCallback, useEffect, type FC, type ReactNode } from 'react';

export type ModalProps = {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  /** Sizes/positions the panel — defaults to a large, mostly-full-screen sheet. */
  className?: string;
  labelledBy?: string;
};

/**
 * Generic overlay: backdrop + scrollable panel, closes on Escape or backdrop
 * click, locks body scroll while open. Panel sizing/content is up to the caller.
 */
export const Modal: FC<ModalProps> = ({
  open,
  onClose,
  children,
  className,
  labelledBy,
}) => {
  const handleClose = useCallback(() => onClose(), [onClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, handleClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-pointer bg-black/60"
        aria-label="Dismiss dialog"
        onClick={handleClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        className={cn(
          'border-border bg-background relative z-10 max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-xl border shadow-xl',
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
};
