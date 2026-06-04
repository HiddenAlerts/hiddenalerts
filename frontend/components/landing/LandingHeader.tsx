import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import Link from 'next/link';

import { LandingLogo } from './LandingLogo';

type LandingHeaderProps = {
  /** When false, hides the Login/Sign up actions (e.g. on auth pages). */
  showAuthActions?: boolean;
};

export function LandingHeader({ showAuthActions = true }: LandingHeaderProps) {
  return (
    <header className="border-border-subtle bg-background/80 sticky top-0 z-50 border-b backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between gap-3 px-4 md:px-6">
        <Link
          href="/"
          className="focus-visible:ring-primary-500 rounded-md focus-visible:ring-2 focus-visible:outline-none"
        >
          <LandingLogo />
        </Link>
        {showAuthActions ? (
          <nav
            className="flex shrink-0 items-center gap-2"
            aria-label="Account actions"
          >
            <Link
              href="/login"
              className={cn(
                buttonVariants({ variant: 'outline', size: 'sm' }),
                'h-8 px-3 text-xs md:h-9 md:px-4 md:text-sm',
              )}
            >
              Login
            </Link>
            <Link
              href="/signup"
              className={cn(
                buttonVariants({ variant: 'default', size: 'sm' }),
                'h-8 px-3 text-xs md:h-9 md:px-4 md:text-sm',
              )}
            >
              Sign up
            </Link>
          </nav>
        ) : null}
      </div>
    </header>
  );
}
