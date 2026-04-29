'use client';

import { Button, Input } from '@/components';
import { cn } from '@/lib/utils';
import { Mail, X } from 'lucide-react';
import {
  type FC,
  type FormEvent,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';
import { toast } from 'sonner';

export type EarlyAccessModalProps = {
  open: boolean;
  onClose: () => void;
};

export const EarlyAccessModal: FC<EarlyAccessModalProps> = ({
  open,
  onClose,
}) => {
  const titleId = useId();
  const [email, setEmail] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleClose = useCallback(() => {
    setEmail('');
    onClose();
  }, [onClose]);

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
    const id = window.requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(id);
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

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    toast.success('Thanks — we will be in touch.');
    handleClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/50"
        aria-label="Dismiss dialog"
        onClick={handleClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="border-border bg-surface relative z-10 w-full max-w-md rounded-xl border p-6 shadow-xl"
      >
        <button
          type="button"
          onClick={handleClose}
          className="text-muted hover:text-foreground hover:bg-surface-muted absolute top-3 right-3 inline-flex size-9 items-center justify-center rounded-md transition-colors"
          aria-label="Close"
        >
          <X className="size-5" aria-hidden />
        </button>

        <h2
          id={titleId}
          className="font-heading text-foreground pr-10 text-lg font-semibold tracking-tight"
        >
          Get Early Access to High-Risk Fraud Signals
        </h2>
        <p className="text-muted mt-2 text-sm leading-relaxed">
          Early fraud signals before they hit the news.
        </p>

        <form className="mt-5 flex flex-col gap-3" onSubmit={handleSubmit}>
          <Input
            ref={inputRef}
            name="early-access-email"
            type="email"
            inputSize="md"
            placeholder="Enter your email"
            autoComplete="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
            leftIcon={<Mail className="size-4" aria-hidden />}
            parentStyles="w-full"
            aria-label="Email address"
          />
          <Button
            type="submit"
            variant="default"
            size="md"
            className={cn(
              'w-full border-transparent bg-danger text-white hover:border-transparent hover:bg-danger/90 active:bg-danger/80',
            )}
          >
            Submit
          </Button>
        </form>
      </div>
    </div>
  );
};
