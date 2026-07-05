import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import Link from 'next/link';

import type { LandingNavItem } from '@/data/landing';

import { LandingLogo } from './LandingLogo';

type LandingHeaderProps = {
  /** When false, hides the Login/Sign up actions (e.g. on auth pages). */
  showAuthActions?: boolean;
  /**
   * Marketing nav links (e.g. How It Works, Pricing). When provided, the header
   * renders the full marketing layout with a single primary CTA. When omitted,
   * it falls back to the simple Login/Sign up layout used on auth pages.
   */
  navItems?: ReadonlyArray<LandingNavItem>;
  /** Primary CTA shown alongside the marketing nav. */
  primaryCta?: { label: string; href: string };
};

const ctaClass = (variant: 'default' | 'outline') =>
  cn(
    buttonVariants({ variant, size: 'sm' }),
    'h-8 px-3 text-xs md:h-9 md:px-4 md:text-sm',
  );

export function LandingHeader({
  showAuthActions = true,
  navItems,
  primaryCta = { label: 'Get Early Access', href: '/signup' },
}: LandingHeaderProps) {
  const isMarketing = Boolean(navItems && navItems.length > 0);

  return (
    <header className="border-border-subtle bg-background/80 sticky top-0 z-50 border-b backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4 md:px-6">
        <Link
          href="/"
          className="focus-visible:ring-primary-500 rounded-md focus-visible:ring-2 focus-visible:outline-none"
        >
          <LandingLogo trademark={isMarketing} />
        </Link>

        {isMarketing ? (
          <>
            <nav
              className="text-muted hidden items-center gap-6 text-sm font-medium md:flex"
              aria-label="Primary"
            >
              {navItems!.map(item => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="hover:text-foreground focus-visible:ring-primary-500 rounded-sm transition-colors focus-visible:ring-2 focus-visible:outline-none"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <Link href={primaryCta.href} className={ctaClass('default')}>
              {primaryCta.label}
            </Link>
          </>
        ) : showAuthActions ? (
          <nav
            className="flex shrink-0 items-center gap-2"
            aria-label="Account actions"
          >
            <Link href="/login" className={ctaClass('outline')}>
              Login
            </Link>
            <Link href="/signup" className={ctaClass('default')}>
              Sign up
            </Link>
          </nav>
        ) : null}
      </div>
    </header>
  );
}
