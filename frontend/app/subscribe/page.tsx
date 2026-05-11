import { LandingHeader } from '@/components/landing/LandingHeader';
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import Link from 'next/link';

import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Subscribe — HiddenAlerts',
  description: 'Subscription and signup for HiddenAlerts',
};

export default function SubscribePage() {
  return (
    <>
      <LandingHeader />
      <main className="text-foreground flex flex-1 flex-col items-center justify-center px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-semibold tracking-tight sm:text-3xl">
          Subscription
        </h1>
        <p className="text-muted mx-auto mt-4 max-w-md text-sm leading-relaxed sm:text-base">
          Account signup and checkout will be available here once billing is
          enabled.
        </p>
        <Link
          href="/"
          className={cn(
            buttonVariants({ variant: 'default', size: 'md' }),
            'mt-8 inline-flex h-11 items-center justify-center px-6',
          )}
        >
          Back to home
        </Link>
      </main>
    </>
  );
}
