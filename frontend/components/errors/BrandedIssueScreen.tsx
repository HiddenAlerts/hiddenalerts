'use client';

import { LandingLogo } from '@/components/landing/LandingLogo';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

export type BrandedIssueScreenProps = {
  code: string;
  title: string;
  description: string;
  /** When provided, shows a primary “Try again” action (e.g. `reset` from an error boundary). */
  onRetry?: () => void;
  /** Optional extra content below the description (e.g. dev details). */
  footer?: ReactNode;
};

export const BrandedIssueScreen: FC<BrandedIssueScreenProps> = ({
  code,
  title,
  description,
  onRetry,
  footer,
}) => (
  <main className="flex flex-1 flex-col items-center justify-center px-4 py-16">
    <div
      className={cn(
        'border-border bg-background-alt w-full max-w-md rounded-xl border',
        'border-t-primary-500 shadow-sm',
        'border-t-4 px-8 py-10 text-center',
      )}
    >
      <div className="mb-8 flex justify-center">
        <LandingLogo />
      </div>
      <p className="text-primary-400 font-heading text-sm font-semibold tracking-widest uppercase">
        {code}
      </p>
      <h1 className="font-heading text-foreground mt-2 text-2xl font-semibold tracking-tight">
        {title}
      </h1>
      <p className="text-muted mt-3 text-sm leading-relaxed">{description}</p>
      {footer}
      <div className="mt-8 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
        {onRetry ? (
          <Button type="button" className="sm:min-w-32" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
        <Link
          href="/"
          className={cn(
            buttonVariants({
              variant: onRetry ? 'secondary' : 'default',
              size: 'md',
            }),
            'inline-flex justify-center',
          )}
        >
          Go home
        </Link>
      </div>
    </div>
  </main>
);
