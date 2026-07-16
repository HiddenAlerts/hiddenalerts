import { Check } from 'lucide-react';

import { ANALYST_CONTENT } from '@/data/landing';

import { LandingAlertsPanel } from './LandingAlertsPanel';
import { LandingBriefPreviewCard } from './LandingBriefPreviewCard';
import { LandingSection } from './LandingSection';

export function LandingIntelligencePreview() {
  const analyst = ANALYST_CONTENT;

  return (
    <LandingSection
      id="alerts"
      ariaLabelledby="alerts-heading"
      className="border-border-subtle border-t py-8 md:py-10"
    >
      <div className="flex flex-col gap-5">
        {/* Ken mockup — full-width featured brief preview */}
        <LandingBriefPreviewCard />

        {/* Alerts + Analyst — taller portrait so Ken’s full headshot is visible */}
        <div className="grid items-stretch gap-5 lg:grid-cols-2 lg:gap-5">
          <LandingAlertsPanel />

          <div className="border-border bg-background-alt/80 flex min-h-[560px] flex-col overflow-hidden rounded-2xl border sm:min-h-[600px] lg:min-h-[640px]">
            {/* Portrait-oriented frame + object-top keeps the full head in view */}
            <div className="relative aspect-[3/4] w-full shrink-0 overflow-hidden sm:aspect-[4/5] lg:aspect-auto lg:min-h-[420px] lg:flex-1">
              {/* eslint-disable-next-line @next/next/no-img-element -- marketing portrait asset */}
              <img
                src={analyst.portraitSrc}
                alt={analyst.portraitAlt}
                className="absolute inset-0 size-full object-cover object-top"
              />
              <div
                className="absolute inset-0 bg-gradient-to-t from-[#070d19] via-[#070d19]/45 to-transparent"
                aria-hidden
              />
              <div className="absolute inset-x-0 bottom-0 p-5 sm:p-6">
                <p className="text-primary-400 text-[0.65rem] font-semibold tracking-[0.14em] uppercase">
                  {analyst.eyebrow}
                </p>
                <h3 className="text-foreground mt-2 text-xl font-semibold tracking-tight">
                  {analyst.name}
                </h3>
                <p className="text-muted mt-1 text-sm">{analyst.title}</p>
              </div>
            </div>

            <ul className="shrink-0 space-y-2.5 border-border/60 border-t p-5 sm:p-6">
              {analyst.credentials.map(item => (
                <li
                  key={item}
                  className="text-body flex items-start gap-2.5 text-sm"
                >
                  <Check
                    className="text-info mt-0.5 size-4 shrink-0"
                    aria-hidden
                  />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </LandingSection>
  );
}
