import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';

import { HERO_CONTENT } from '@/data/landing';

import { HeroThreatVisual } from './HeroThreatVisual';

export function LandingHero() {
  return (
    <section
      id="top"
      className="relative scroll-mt-16 overflow-hidden px-4 py-16 md:px-6 md:py-24"
    >
      {/* Ambient background */}
      <div
        className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_85%_25%,rgba(238,68,66,0.16),transparent_45%),radial-gradient(circle_at_10%_10%,rgba(238,68,66,0.08),transparent_40%)]"
        aria-hidden
      />

      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2 lg:gap-10">
        <div className="flex flex-col">
          <span className="text-primary-400 text-xs font-semibold tracking-[0.2em] uppercase">
            {HERO_CONTENT.eyebrow}
          </span>

          <h1 className="font-heading text-foreground mt-4 text-4xl leading-[1.08] font-bold tracking-tight text-balance sm:text-5xl lg:text-[3.4rem]">
            {HERO_CONTENT.titleLead}{' '}
            <span className="text-primary-500">{HERO_CONTENT.titleEmphasis}</span>
          </h1>

          <p className="text-body mt-6 max-w-xl text-base leading-relaxed sm:text-lg">
            {HERO_CONTENT.description}
          </p>
          <p className="text-muted mt-3 max-w-xl text-sm leading-relaxed sm:text-base">
            {HERO_CONTENT.secondaryDescription}
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Link
              href={HERO_CONTENT.primaryCta.href}
              className={cn(
                buttonVariants({ variant: 'default', size: 'md' }),
                'h-12 gap-2 px-6 text-sm font-semibold sm:text-base',
              )}
            >
              {HERO_CONTENT.primaryCta.label}
              <ArrowRight className="size-4" aria-hidden />
            </Link>
            <Link
              href={HERO_CONTENT.secondaryCta.href}
              className={cn(
                buttonVariants({ variant: 'outline', size: 'md' }),
                'border-border bg-surface/40 text-foreground hover:bg-surface/70 hover:border-border h-12 px-6 text-sm font-semibold sm:text-base',
              )}
            >
              {HERO_CONTENT.secondaryCta.label}
            </Link>
          </div>

          <p className="text-muted-foreground mt-3 text-xs">
            {HERO_CONTENT.ctaFootnote}
          </p>

          <dl className="mt-8 grid gap-3 sm:grid-cols-2">
            {HERO_CONTENT.tiers.map(tier => (
              <div
                key={tier.label}
                className="border-border bg-surface/40 rounded-xl border p-4"
              >
                <dt className="flex items-center gap-2">
                  <span className="bg-primary-500/15 text-primary-300 rounded-md px-2 py-0.5 text-xs font-semibold">
                    {tier.label}
                  </span>
                  <span className="text-foreground text-sm font-semibold">
                    {tier.title}
                  </span>
                </dt>
                <dd className="text-muted mt-1.5 text-xs leading-relaxed">
                  {tier.description}
                </dd>
              </div>
            ))}
          </dl>

          <p className="text-muted-foreground mt-6 text-sm">
            {HERO_CONTENT.trustLine}
          </p>
        </div>

        <HeroThreatVisual className="order-first lg:order-none" />
      </div>
    </section>
  );
}
