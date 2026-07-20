import { buttonVariants } from '@/components/ui/button';
import { HERO_CONTENT, LANDING_LINKS } from '@/data/landing';
import { cn } from '@/lib/utils';
import { Mail } from 'lucide-react';
import Link from 'next/link';

import { HeroThreatVisual } from './HeroThreatVisual';

export function LandingHero() {
  return (
    <section
      id="top"
      className="relative scroll-mt-16 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:py-10"
    >
      <div
        className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_85%_25%,rgba(238,68,66,0.14),transparent_45%),radial-gradient(circle_at_10%_10%,rgba(79,140,255,0.08),transparent_40%),radial-gradient(ellipse_at_50%_100%,rgba(13,21,37,0.9),transparent_55%)]"
        aria-hidden
      />

      <div className="mx-auto grid max-w-6xl items-center gap-5 lg:grid-cols-2 lg:gap-6">
        <div className="flex flex-col">
          <span className="text-primary-400 text-xs font-semibold tracking-[0.2em] uppercase">
            {HERO_CONTENT.eyebrow}
          </span>

          <h1 className="font-heading text-foreground mt-2 text-3xl leading-[1.08] font-bold tracking-tight text-balance sm:text-4xl lg:text-[2.65rem]">
            {HERO_CONTENT.titleLead}{' '}
            <span className="text-primary-500">{HERO_CONTENT.titleEmphasis}</span>
          </h1>

          <p className="text-body mt-3 max-w-xl text-sm leading-relaxed sm:text-base">
            {HERO_CONTENT.description}
          </p>

          <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:items-center">
            <Link
              href={LANDING_LINKS.heroSubscribe}
              className={cn(
                buttonVariants({ variant: 'default', size: 'md' }),
                'h-10 gap-2 px-4 text-sm font-semibold',
              )}
            >
              <Mail className="size-4" aria-hidden />
              {HERO_CONTENT.ctaLabel}
            </Link>
            <p className="text-muted-foreground text-xs sm:max-w-xs">
              {HERO_CONTENT.emailFootnote}
            </p>
          </div>
        </div>

        <HeroThreatVisual className="order-first lg:order-none" />
      </div>
    </section>
  );
}
