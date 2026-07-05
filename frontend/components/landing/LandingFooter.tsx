import { dashboardFooterContent as c } from '@/content/legal/dashboard-footer';
import { cn } from '@/lib/utils';
import Link from 'next/link';

import { LandingLogo } from './LandingLogo';
import { LinkedInIcon, XIcon } from './SocialIcons';

const legalLinkClass =
  'text-muted-foreground hover:text-body text-sm transition-colors focus-visible:ring-primary-500 rounded-sm focus-visible:ring-2 focus-visible:outline-none';

const primaryLinks = [
  { href: c.linkDisclaimerHref, label: c.linkDisclaimerLabel },
  { href: c.linkPrivacyHref, label: c.linkPrivacyLabel },
  { href: c.linkContactHref, label: c.linkContactLabel },
] as const;

const secondaryLinks = [
  { href: c.linkTermsHref, label: c.linkTermsLabel },
  { href: c.linkSupportHref, label: c.linkSupportLabel },
] as const;

const socialLinks = [
  {
    href: 'https://www.linkedin.com/company/covertlytics',
    label: 'LinkedIn',
    icon: LinkedInIcon,
  },
  {
    href: 'https://x.com/covertlytics',
    label: 'X (Twitter)',
    icon: XIcon,
  },
] as const;

export function LandingFooter() {
  return (
    <footer
      className="border-border-subtle bg-background-alt/95 mt-auto border-t"
      aria-label="Site footer"
    >
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-12 md:py-14">
        <div className="grid gap-10 md:grid-cols-[1.4fr_1fr_1fr] md:gap-12">
          {/* Brand + disclaimer */}
          <div className="flex flex-col gap-3">
            <Link
              href="/"
              className="focus-visible:ring-primary-500 inline-flex w-fit rounded-md focus-visible:ring-2 focus-visible:outline-none"
            >
              <LandingLogo trademark />
            </Link>
            <p className="text-muted-foreground text-xs leading-relaxed sm:text-sm">
              {c.descriptionLine1}
            </p>
            <p className="text-muted-foreground text-xs leading-relaxed sm:text-sm">
              {c.descriptionLine2}
            </p>
            <p className="text-muted-foreground text-xs leading-relaxed sm:text-sm">
              {c.productAttributionBefore}
              <span className="text-body">{c.productAttributionCompany}</span>
            </p>
          </div>

          {/* Legal links */}
          <nav aria-label="Legal links" className="flex flex-col gap-2">
            {primaryLinks.map(link => (
              <Link key={link.href} href={link.href} className={legalLinkClass}>
                {link.label}
              </Link>
            ))}
          </nav>

          <nav aria-label="Support links" className="flex flex-col gap-2">
            {secondaryLinks.map(link => (
              <Link key={link.href} href={link.href} className={legalLinkClass}>
                {link.label}
              </Link>
            ))}
          </nav>
        </div>

        {/* Social + copyright */}
        <div className="border-border-subtle mt-10 flex flex-col items-center justify-between gap-4 border-t pt-6 sm:flex-row">
          <div className="flex items-center gap-3">
            {socialLinks.map(({ href, label, icon: Icon }) => (
              <a
                key={href}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={label}
                className={cn(
                  'text-muted hover:text-foreground border-border bg-surface/50 flex size-9 items-center justify-center rounded-full border transition-colors',
                )}
              >
                <Icon />
              </a>
            ))}
          </div>
          <p className="text-muted-foreground text-xs sm:text-sm">
            {c.copyrightPrefix}
            {c.copyrightCompany}. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
