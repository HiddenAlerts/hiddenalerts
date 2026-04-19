import Link from 'next/link';

import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import { LandingLogo } from './LandingLogo';

export function LandingHeader() {
  return (
    <header className="border-border-subtle bg-background/80 sticky top-0 z-50 border-b backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="focus-visible:ring-primary-500 rounded-md focus-visible:ring-2 focus-visible:outline-none"
        >
          <LandingLogo />
        </Link>
        <Link
          href="#waitlist"
          className={cn(buttonVariants({ variant: 'default', size: 'sm' }))}
        >
          Join waitlist
        </Link>
      </div>
    </header>
  );
}
