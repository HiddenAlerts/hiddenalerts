'use client';

import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Menu, X } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { LANDING_LINKS, type LandingNavItem } from '@/data/landing';

import { LandingHashLink } from './LandingHashLink';
import { LandingLogo } from './LandingLogo';

type LandingHeaderProps = {
  showAuthActions?: boolean;
  navItems?: ReadonlyArray<LandingNavItem>;
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
  primaryCta = {
    label: 'Join Free Intelligence Updates',
    href: LANDING_LINKS.heroSubscribe,
  },
}: LandingHeaderProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const isMarketing = Boolean(navItems && navItems.length > 0);

  return (
    <header className="border-border-subtle bg-background/90 sticky top-0 z-50 border-b backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4 md:px-6">
        <Link
          href="/"
          className="focus-visible:ring-primary-500 shrink-0 rounded-md focus-visible:ring-2 focus-visible:outline-none"
        >
          <LandingLogo trademark={isMarketing} />
        </Link>

        {isMarketing ? (
          <>
            <nav
              className="text-muted hidden items-center gap-5 text-sm font-medium lg:flex"
              aria-label="Primary"
            >
              {navItems!.map(item => (
                <LandingHashLink
                  key={item.href}
                  href={item.href}
                  className="hover:text-foreground focus-visible:ring-primary-500 rounded-sm transition-colors focus-visible:ring-2 focus-visible:outline-none"
                >
                  {item.label}
                </LandingHashLink>
              ))}
            </nav>

            <div className="hidden items-center gap-3 lg:flex">
              <Link
                href={LANDING_LINKS.login}
                className="text-muted hover:text-foreground text-sm font-medium transition-colors"
              >
                Log in
              </Link>
              <LandingHashLink
                href={primaryCta.href}
                className={ctaClass('default')}
              >
                {primaryCta.label}
              </LandingHashLink>
            </div>

            <button
              type="button"
              className="text-foreground hover:bg-surface/60 flex size-9 items-center justify-center rounded-md lg:hidden"
              aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen(open => !open)}
            >
              {mobileOpen ? (
                <X className="size-5" />
              ) : (
                <Menu className="size-5" />
              )}
            </button>
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

      {isMarketing && mobileOpen ? (
        <nav
          className="border-border-subtle bg-background/95 border-t px-4 py-4 lg:hidden"
          aria-label="Mobile navigation"
        >
          <ul className="flex flex-col gap-1">
            {navItems!.map(item => (
              <li key={item.href}>
                <LandingHashLink
                  href={item.href}
                  className="text-muted hover:text-foreground hover:bg-surface/40 block rounded-md px-3 py-2.5 text-sm font-medium transition-colors"
                  onClick={() => setMobileOpen(false)}
                >
                  {item.label}
                </LandingHashLink>
              </li>
            ))}
            <li className="border-border-subtle mt-2 border-t pt-3">
              <Link
                href={LANDING_LINKS.login}
                className="text-muted hover:text-foreground block px-3 py-2.5 text-sm font-medium"
                onClick={() => setMobileOpen(false)}
              >
                Log in
              </Link>
            </li>
            <li className="mt-2 px-3">
              <LandingHashLink
                href={primaryCta.href}
                className={cn(ctaClass('default'), 'w-full justify-center')}
                onClick={() => setMobileOpen(false)}
              >
                {primaryCta.label}
              </LandingHashLink>
            </li>
          </ul>
        </nav>
      ) : null}
    </header>
  );
}
