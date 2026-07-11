import { cn } from '@/lib/utils';
import { Lock } from 'lucide-react';

import { HERO_CONTENT, LANDING_LINKS } from '@/data/landing';

import { LandingEmailForm } from './LandingEmailForm';
import { HeroThreatVisual } from './HeroThreatVisual';

export function LandingHero() {
  return (
    <section
      id="top"
      className="relative scroll-mt-16 overflow-hidden px-4 py-12 md:px-6 md:py-20 lg:py-24"
    >
      <div
        className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_85%_25%,rgba(238,68,66,0.14),transparent_45%),radial-gradient(circle_at_10%_10%,rgba(238,68,66,0.06),transparent_40%)]"
        aria-hidden
      />

      <div className="mx-auto grid max-w-6xl items-center gap-10 lg:grid-cols-2 lg:gap-12">
        <div className="flex flex-col">
          <span className="text-primary-400 text-xs font-semibold tracking-[0.2em] uppercase">
            {HERO_CONTENT.eyebrow}
          </span>

          <h1 className="font-heading text-foreground mt-4 text-4xl leading-[1.08] font-bold tracking-tight text-balance sm:text-5xl lg:text-[3.25rem]">
            {HERO_CONTENT.titleLead}{' '}
            <span className="text-primary-500">{HERO_CONTENT.titleEmphasis}</span>
          </h1>

          <p className="text-body mt-5 max-w-xl text-base leading-relaxed sm:text-lg">
            {HERO_CONTENT.description}
          </p>

          <div className="mt-8">
            <LandingEmailForm
              actionUrl={LANDING_LINKS.newsletter}
              placeholder={HERO_CONTENT.emailPlaceholder}
              buttonLabel={HERO_CONTENT.emailButtonLabel}
              buttonClassName="sm:px-4 sm:text-xs md:text-sm"
            />
            <p className="text-muted-foreground mt-2.5 flex items-center gap-1.5 text-xs">
              <Lock className="size-3 shrink-0" aria-hidden />
              {HERO_CONTENT.emailFootnote}
            </p>
          </div>

          <div className="mt-8">
            <p className="text-muted text-sm">{HERO_CONTENT.trustLine}</p>
            <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-3">
              {HERO_CONTENT.trustItems.map(item => {
                const Icon = item.icon;
                return (
                  <li
                    key={item.label}
                    className="text-muted flex items-center gap-2 text-sm"
                  >
                    <Icon className="text-muted-foreground size-4 shrink-0" aria-hidden />
                    <span>{item.label}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>

        <HeroThreatVisual className="order-first lg:order-none" />
      </div>
    </section>
  );
}
