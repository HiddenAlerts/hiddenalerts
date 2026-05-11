import { dashboardFooterContent as c } from '@/content/legal/dashboard-footer';
import Link from 'next/link';
import { Fragment } from 'react';

import { LandingLogo } from './LandingLogo';

const legalLinks = [
  { href: c.linkDisclaimerHref, label: c.linkDisclaimerLabel },
  { href: c.linkTermsHref, label: c.linkTermsLabel },
  { href: c.linkPrivacyHref, label: c.linkPrivacyLabel },
] as const;

const contactLinkClass =
  'text-body hover:text-foreground text-sm font-medium underline decoration-transparent underline-offset-2 transition-[color,text-decoration-color] hover:decoration-foreground/30 focus-visible:ring-primary-500 rounded-sm focus-visible:ring-2 focus-visible:outline-none';

const legalLinkClass =
  'text-muted-foreground hover:text-body text-sm underline decoration-transparent underline-offset-2 transition-[color,text-decoration-color] hover:decoration-body/40 focus-visible:ring-primary-500 rounded-sm focus-visible:ring-2 focus-visible:outline-none';

export function LandingFooter() {
  return (
    <footer
      className="border-border-subtle bg-background-alt/95 mt-auto border-t"
      aria-label="Site footer"
    >
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-12 md:py-14">
        <div className="flex flex-col gap-10 md:flex-row md:justify-between md:gap-14 lg:gap-20">
          <div className="flex max-w-md flex-col gap-3 text-center md:text-left">
            <Link
              href="/"
              className="focus-visible:ring-primary-500 mx-auto inline-flex w-fit rounded-md focus-visible:ring-2 focus-visible:outline-none md:mx-0"
            >
              <LandingLogo trademark />
            </Link>
            <p className="text-body text-sm leading-relaxed">
              Early warning intelligence and hidden risk monitoring.
            </p>
            <p className="text-body text-sm leading-relaxed">
              HiddenAlerts is a product of Covertlytics, LLC.
            </p>
            <p className="text-muted-foreground text-sm leading-relaxed">
              Signal-based intelligence derived from public data.
            </p>
            <p className="text-muted-foreground text-sm leading-relaxed">
              For informational purposes only. Not financial or legal advice.
            </p>
            <p className="text-muted-foreground mt-1 text-sm">
              © 2026 Covertlytics LLC
            </p>
          </div>

          <div className="flex flex-col items-center gap-6 md:items-end">
            <nav
              className="flex flex-col items-center gap-2 sm:flex-row sm:gap-6 md:items-end"
              aria-label="Contact"
            >
              <a
                href="mailto:support@covertlytics.com"
                className={contactLinkClass}
              >
                Support
              </a>
              <a
                href="mailto:contact@covertlytics.com"
                className={contactLinkClass}
              >
                Contact
              </a>
            </nav>

            <nav
              className="flex flex-wrap items-center justify-center gap-y-1 md:justify-end"
              aria-label="Legal links"
            >
              {legalLinks.map((item, index) => (
                <Fragment key={item.href}>
                  {index > 0 ? (
                    <span
                      aria-hidden
                      className="text-muted-foreground/40 select-none px-2 text-[0.65rem] leading-none"
                    >
                      ·
                    </span>
                  ) : null}
                  <Link href={item.href} className={legalLinkClass}>
                    {item.label}
                  </Link>
                </Fragment>
              ))}
            </nav>
          </div>
        </div>
      </div>
    </footer>
  );
}
