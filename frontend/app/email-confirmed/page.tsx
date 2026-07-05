'use client';

import { LandingFooter } from '@/components/landing/LandingFooter';
import { LandingHeader } from '@/components/landing/LandingHeader';
import { Button } from '@/components/ui/button';
import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/contexts/AuthProvider';
import { CheckCircle2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

const SUBSCRIBED_REDIRECT = '/dashboard';
const UNSUBSCRIBED_REDIRECT = '/subscribe';

export default function EmailConfirmedPage() {
  const router = useRouter();
  const { status, subscriber } = useAuth();

  useEffect(() => {
    if (status !== 'authenticated') return;
    const target =
      subscriber?.has_active_subscription === false
        ? UNSUBSCRIBED_REDIRECT
        : SUBSCRIBED_REDIRECT;
    const id = window.setTimeout(() => router.replace(target), 2500);
    return () => window.clearTimeout(id);
  }, [status, subscriber, router]);

  return (
    <>
      <LandingHeader />
      <main className="text-foreground bg-background relative flex flex-1 flex-col items-center justify-center px-4 py-12 sm:py-16">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
        >
          <div className="bg-primary-500/20 absolute -top-32 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full blur-3xl" />
          <div className="bg-info-500/10 absolute right-1/3 bottom-0 h-64 w-64 rounded-full blur-3xl" />
        </div>

        <div className="border-border bg-surface/70 w-full max-w-md rounded-lg border p-6 text-center shadow-md backdrop-blur sm:p-8">
          {status === 'loading' ? (
            <LoadingState label="Confirming your email…" />
          ) : status === 'authenticated' ? (
            <ConfirmedView
              ctaHref={
                subscriber?.has_active_subscription === false
                  ? UNSUBSCRIBED_REDIRECT
                  : SUBSCRIBED_REDIRECT
              }
              ctaLabel={
                subscriber?.has_active_subscription === false
                  ? 'Choose a plan'
                  : 'Go to dashboard'
              }
            />
          ) : (
            <UnauthenticatedView />
          )}
        </div>
      </main>
      <LandingFooter />
    </>
  );
}

function ConfirmedView({
  ctaHref,
  ctaLabel,
}: {
  ctaHref: string;
  ctaLabel: string;
}) {
  return (
    <div className="flex flex-col items-center gap-4">
      <span className="bg-primary-500/15 text-primary-400 inline-flex size-14 items-center justify-center rounded-full">
        <CheckCircle2 className="size-7" aria-hidden />
      </span>
      <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
        Email confirmed
      </h1>
      <p className="text-muted text-sm leading-relaxed sm:text-base">
        Thanks — your email is verified. We’ll take you to the next step in
        a moment.
      </p>
      <Link href={ctaHref} className="mt-2 inline-flex w-full">
        <Button type="button" variant="default" className="w-full">
          {ctaLabel}
        </Button>
      </Link>
    </div>
  );
}

function UnauthenticatedView() {
  return (
    <div className="flex flex-col items-center gap-4">
      <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
        Email confirmed
      </h1>
      <p className="text-muted text-sm leading-relaxed sm:text-base">
        Your email has been verified. Sign in to continue.
      </p>
      <Link href="/login" className="mt-2 inline-flex w-full">
        <Button type="button" variant="default" className="w-full">
          Sign in
        </Button>
      </Link>
    </div>
  );
}
