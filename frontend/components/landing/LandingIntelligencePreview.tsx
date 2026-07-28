import { ANALYST_CONTENT } from '@/data/landing';
import { Check } from 'lucide-react';

import { LandingAlertsPanel } from './LandingAlertsPanel';
import { LandingBriefPreviewCard } from './LandingBriefPreviewCard';
import { LandingSection } from './LandingSection';

/**
 * Approved final mockup: three equal columns —
 * Latest High-Risk Alerts | Intelligence Brief Preview | Lead Analyst.
 */
export function LandingIntelligencePreview() {
  const analyst = ANALYST_CONTENT;

  return (
    <LandingSection
      ariaLabelledby="alerts-heading"
      className="border-border-subtle border-t py-8 md:py-10"
      containerClassName="max-w-7xl"
    >
      <div className="grid items-stretch gap-4 lg:grid-cols-3 lg:gap-5">
        <LandingAlertsPanel />
        <LandingBriefPreviewCard />

        <aside className="border-border bg-background-alt/80 flex h-full min-h-[320px] flex-col rounded-xl border p-5 sm:p-6">
          <h2 className="text-info shrink-0 text-[0.7rem] font-bold tracking-[0.16em] uppercase">
            {analyst.eyebrow}
          </h2>

          {/* Stacked: portrait on top, bio/credentials below */}
          <div className="mt-4 flex min-h-0 flex-1 flex-col gap-4">
            <div className="relative min-h-[200px] flex-1 overflow-hidden rounded-md bg-[#070d19]">
              {/* eslint-disable-next-line @next/next/no-img-element -- marketing portrait asset */}
              <img
                src={analyst.portraitSrc}
                alt={analyst.portraitAlt}
                className="absolute inset-0 size-full object-contain object-top"
              />
              <div
                className="pointer-events-none absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-[#070d19] via-[#070d19]/40 to-transparent"
                aria-hidden
              />
            </div>

            <div className="shrink-0">
              <h3 className="text-foreground text-lg font-semibold tracking-tight sm:text-xl">
                {analyst.name}
              </h3>
              <p className="text-muted mt-1 text-sm leading-snug">
                {analyst.title}
              </p>

              <ul className="mt-3 space-y-2">
                {analyst.credentials.map(item => (
                  <li
                    key={item}
                    className="text-foreground flex items-start gap-2 text-sm leading-snug"
                  >
                    <Check
                      className="text-info mt-0.5 size-4 shrink-0"
                      strokeWidth={2.5}
                      aria-hidden
                    />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </aside>
      </div>
    </LandingSection>
  );
}
