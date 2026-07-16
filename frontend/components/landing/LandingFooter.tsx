import { cn } from '@/lib/utils';
import { Mail, Shield } from 'lucide-react';
import Link from 'next/link';
import type { ReactNode } from 'react';

import { FOOTER_CONTENT } from '@/data/landing';

import { LandingLogo } from './LandingLogo';
import { LandingNewsletterForm } from './LandingNewsletterForm';
import { LinkedInIcon, XIcon } from './SocialIcons';

const linkClass =
  'text-muted-foreground hover:text-body text-sm transition-colors focus-visible:ring-primary-500 rounded-sm focus-visible:ring-2 focus-visible:outline-none';

const columnTitleClass =
  'text-muted-foreground text-xs font-semibold tracking-[0.14em] uppercase';

function isExternalHref(href: string) {
  return (
    href.startsWith('http://') ||
    href.startsWith('https://') ||
    href.startsWith('mailto:')
  );
}

function FooterLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  if (isExternalHref(href)) {
    const isMail = href.startsWith('mailto:');
    return (
      <a
        href={href}
        className={linkClass}
        {...(isMail
          ? {}
          : { target: '_blank', rel: 'noopener noreferrer' })}
      >
        {children}
      </a>
    );
  }

  return (
    <Link href={href} className={linkClass}>
      {children}
    </Link>
  );
}

export function LandingFooter() {
  const c = FOOTER_CONTENT;

  return (
    <footer
      className="border-border-subtle bg-background-alt/95 mt-auto border-t"
      aria-label="Site footer"
    >
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 md:py-12">
        <div className="grid gap-10 lg:grid-cols-[1.5fr_1fr_1fr_1fr_1fr] lg:gap-8">
          {/* Brand */}
          <div className="flex flex-col gap-4 lg:col-span-1">
            <Link
              href="/"
              className="focus-visible:ring-primary-500 inline-flex w-fit rounded-md focus-visible:ring-2 focus-visible:outline-none"
            >
              <LandingLogo trademark />
            </Link>
            <p className="text-muted-foreground max-w-xs text-sm leading-relaxed">
              {c.tagline}
            </p>
            <div className="flex items-center gap-3">
              <a
                href={c.socialLinks[0].href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={c.socialLinks[0].label}
                className={cn(
                  'text-muted hover:text-foreground border-border bg-surface/50 flex size-9 items-center justify-center rounded-full border transition-colors',
                )}
              >
                <LinkedInIcon />
              </a>
              <a
                href={c.socialLinks[1].href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={c.socialLinks[1].label}
                className={cn(
                  'text-muted hover:text-foreground border-border bg-surface/50 flex size-9 items-center justify-center rounded-full border transition-colors',
                )}
              >
                <XIcon />
              </a>
              <a
                href={c.socialLinks[2].href}
                aria-label={c.socialLinks[2].label}
                className={cn(
                  'text-muted hover:text-foreground border-border bg-surface/50 flex size-9 items-center justify-center rounded-full border transition-colors',
                )}
              >
                <Mail className="size-4" />
              </a>
            </div>
          </div>

          {/* Product */}
          <nav aria-label="Product links" className="flex flex-col gap-3">
            <p className={columnTitleClass}>Product</p>
            {c.productLinks.map(link => (
              <FooterLink key={link.href + link.label} href={link.href}>
                {link.label}
              </FooterLink>
            ))}
          </nav>

          {/* Resources */}
          <nav aria-label="Resource links" className="flex flex-col gap-3">
            <p className={columnTitleClass}>Resources</p>
            {c.resourceLinks.map(link => (
              <FooterLink key={link.href + link.label} href={link.href}>
                {link.label}
              </FooterLink>
            ))}
          </nav>

          {/* Legal */}
          <nav aria-label="Legal links" className="flex flex-col gap-3">
            <p className={columnTitleClass}>Legal</p>
            {c.legalLinks.map(link => (
              <FooterLink key={link.href + link.label} href={link.href}>
                {link.label}
              </FooterLink>
            ))}
          </nav>

          {/* Contact */}
          <nav aria-label="Contact links" className="flex flex-col gap-3">
            <p className={columnTitleClass}>Contact</p>
            {c.contactLinks.map(link => (
              <FooterLink key={link.href + link.label} href={link.href}>
                {link.label}
              </FooterLink>
            ))}
          </nav>
        </div>

        {/* Newsletter row */}
        <div className="border-border-subtle mt-8 grid gap-6 border-t pt-8 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <p className="text-foreground text-sm font-semibold tracking-wide uppercase">
              {c.newsletterTitle}
            </p>
            <p className="text-muted-foreground mt-1 text-sm">
              {c.newsletterDescription}
            </p>
          </div>
          <LandingNewsletterForm
            id="newsletter"
            className="w-full lg:max-w-lg"
            ariaLabel="Footer newsletter signup"
            variant="compact"
          />
        </div>

        {/* Bottom bar */}
        <div className="border-border-subtle mt-8 flex flex-col items-center justify-between gap-4 border-t pt-6 sm:flex-row">
          <p className="text-muted-foreground text-xs sm:text-sm">{c.copyright}</p>
          <p className="text-muted-foreground flex items-center gap-2 text-xs sm:text-sm">
            <Shield className="text-muted size-4 shrink-0" aria-hidden />
            {c.securityNote}
          </p>
        </div>
      </div>
    </footer>
  );
}
