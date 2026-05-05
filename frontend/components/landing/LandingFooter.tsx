import Link from 'next/link';

import { LandingLogo } from './LandingLogo';

export function LandingFooter() {
  const year = new Date().getFullYear();

  return (
    <footer
      className="border-border-subtle bg-background-alt/95 mt-auto border-t"
      aria-label="Site footer"
    >
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-12 md:py-14">
        <div className="flex flex-col gap-8 md:flex-row md:items-stretch md:justify-between md:gap-12 lg:gap-16">
          <div className="flex flex-col items-center gap-4 md:items-start">
            <Link
              href="/"
              className="focus-visible:ring-primary-500 inline-flex w-fit rounded-md focus-visible:ring-2 focus-visible:outline-none"
            >
              <LandingLogo />
            </Link>
            <nav
              className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 md:justify-start"
              aria-label="Footer"
            >
              <Link
                href="#waitlist"
                className="text-body hover:text-foreground text-sm font-medium transition-colors"
              >
                Early access
              </Link>
            </nav>
          </div>

          <div className="border-border-subtle flex flex-col gap-3 border-t pt-8 md:max-w-md md:border-t-0 md:border-l md:pt-0 md:pl-10 lg:pl-14">
            <p className="text-body text-center text-sm leading-snug md:text-left">
              © {year} HiddenAlerts. All rights reserved.
            </p>
            <p className="text-muted-foreground text-center text-sm leading-relaxed md:text-left">
              HiddenAlerts is a product of Covertlytics, LLC.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
