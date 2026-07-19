'use client';

import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Check, Loader2, Mail } from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';

type LandingNewsletterFormProps = {
  /** Anchor target for header / in-page CTAs. */
  id?: string;
  className?: string;
  ariaLabel?: string;
  /** Compact footer layout vs pricing card. */
  variant?: 'default' | 'compact';
};

type SubmitState = 'idle' | 'loading' | 'success' | 'error';

/**
 * Custom HiddenAlerts newsletter signup — posts to /api/newsletter.
 * No MailerLite embed, popup, or branding.
 */
export function LandingNewsletterForm({
  id,
  className,
  ariaLabel = 'Join free intelligence updates',
  variant = 'default',
}: LandingNewsletterFormProps) {
  const generatedId = useId();
  const [email, setEmail] = useState('');
  const [state, setState] = useState<SubmitState>('idle');
  const [error, setError] = useState<string | null>(null);
  const fieldId = `${id ?? generatedId}-email`;
  const errorId = `${fieldId}-error`;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state === 'loading') return;

    const normalizedEmail = email.trim();
    if (!normalizedEmail) {
      setState('error');
      setError('Please enter a valid email address.');
      return;
    }

    setState('loading');
    setError(null);

    try {
      const res = await fetch('/api/newsletter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail }),
      });
      const data = (await res.json().catch(() => null)) as {
        error?: string;
      } | null;

      if (!res.ok) {
        setState('error');
        setError(data?.error ?? 'Unable to subscribe. Please try again.');
        return;
      }

      setState('success');
      setEmail('');
    } catch {
      setState('error');
      setError('Unable to subscribe. Please try again.');
    }
  }

  if (state === 'success') {
    return (
      <div
        id={id}
        className={cn(
          'scroll-mt-20 rounded-lg border border-success/40 bg-success-muted/40 px-4 py-3',
          className,
        )}
        role="status"
        aria-live="polite"
      >
        <p className="text-foreground flex items-start gap-2 text-sm font-medium">
          <Check className="text-success mt-0.5 size-4 shrink-0" aria-hidden />
          Thank you for subscribing to HiddenAlerts Intelligence Updates.
        </p>
      </div>
    );
  }

  return (
    <div
      id={id}
      className={cn('scroll-mt-20 w-full min-w-0', className)}
      aria-label={ariaLabel}
    >
      <form
        onSubmit={onSubmit}
        className="flex w-full flex-col gap-2 sm:flex-row sm:items-stretch"
        aria-busy={state === 'loading'}
      >
        <label className="sr-only" htmlFor={fieldId}>
          Email address
        </label>
        <input
          id={fieldId}
          type="email"
          name="email"
          autoComplete="email"
          required
          value={email}
          onChange={e => {
            setEmail(e.target.value);
            if (state === 'error') {
              setState('idle');
              setError(null);
            }
          }}
          placeholder="Enter your email"
          disabled={state === 'loading'}
          aria-invalid={state === 'error'}
          aria-describedby={error ? errorId : undefined}
          className="border-border bg-surface text-foreground placeholder:text-muted-foreground focus-visible:ring-primary-500 h-11 w-full min-w-0 rounded-md border px-3 text-sm outline-none focus-visible:ring-2 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={state === 'loading'}
          className={cn(
            buttonVariants({ variant: 'default', size: 'md' }),
            'h-11 w-full shrink-0 gap-2 px-4 text-sm font-semibold sm:w-auto',
            variant === 'compact' && 'sm:px-5',
          )}
        >
          {state === 'loading' ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <Mail className="size-4" aria-hidden />
          )}
          {state === 'loading'
            ? 'Joining…'
            : 'Join Free Intelligence Updates'}
        </button>
      </form>
      {error ? (
        <p id={errorId} className="text-danger mt-2 text-xs" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
