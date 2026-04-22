import Link from 'next/link';

import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import { LandingLogo } from './LandingLogo';

export function LandingHeader() {
  return (
    <header className="border-border-subtle bg-background/80 sticky top-0 z-50 border-b backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 md:px-6">
        <Link
          href="/"
          className="focus-visible:ring-primary-500 rounded-md focus-visible:ring-2 focus-visible:outline-none"
        >
          <LandingLogo />
        </Link>
        <Link
          href="#waitlist"
          className={cn(
            buttonVariants({ variant: 'default', size: 'sm' }),
            'h-8 shrink-0 px-3 py-0 text-xs md:h-auto md:px-6 md:py-2 md:text-sm',
          )}
        >
          Get Early Access
        </Link>
      </div>
    </header>
  );
}
