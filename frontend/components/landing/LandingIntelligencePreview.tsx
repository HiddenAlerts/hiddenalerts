import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Check, ExternalLink } from 'lucide-react';

import {
  ANALYST_CONTENT,
  INTELLIGENCE_BRIEF_PREVIEW,
  LIVE_ALERTS,
  LIVE_ALERTS_PANEL,
} from '@/data/landing';

import { LandingLiveAlertRow } from './LandingLiveAlertRow';
import { LandingSection } from './LandingSection';

export function LandingIntelligencePreview() {
  const brief = INTELLIGENCE_BRIEF_PREVIEW;
  const analyst = ANALYST_CONTENT;

  return (
    <LandingSection
      id="alerts"
      ariaLabelledby="alerts-heading"
      className="border-border-subtle border-t py-10 md:py-12"
    >
      <div className="grid gap-5 lg:grid-cols-3 lg:gap-5">
        {/* Latest high-risk alerts — preview only */}
        <div className="border-border bg-background-alt/80 flex flex-col rounded-2xl border p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <h2
              id="alerts-heading"
              className="text-primary-400 text-xs font-semibold tracking-[0.14em] uppercase"
            >
              {LIVE_ALERTS_PANEL.title}
            </h2>
            <span className="text-info border-info/30 bg-info/10 rounded-full border px-2 py-0.5 text-[0.65rem] font-semibold tracking-wide">
              {LIVE_ALERTS_PANEL.badge}
            </span>
          </div>

          <div className="mt-1 flex-1">
            {LIVE_ALERTS.map((alert, i) => (
              <LandingLiveAlertRow key={i} alert={alert} />
            ))}
          </div>

          <p className="text-muted-foreground mt-4 border-border/50 border-t pt-3 text-xs leading-relaxed">
            {LIVE_ALERTS_PANEL.footnote}
          </p>
        </div>

        {/* Intelligence brief preview */}
        <div
          id="intelligence-brief"
          className="border-primary-500/50 bg-background-alt/80 scroll-mt-24 flex flex-col rounded-2xl border p-5 sm:p-6"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-primary-400 text-xs font-semibold tracking-[0.14em] uppercase">
              {brief.eyebrow}
            </span>
            <span className="border-danger/40 bg-danger-muted text-danger rounded-full border px-3 py-1 text-xs font-semibold">
              Risk Score: {brief.score}/100
            </span>
          </div>

          <h3 className="text-foreground mt-4 text-base leading-snug font-semibold sm:text-lg">
            {brief.title}
          </h3>
          <p className="text-muted-foreground mt-2 text-xs">{brief.date}</p>

          <p className="text-body mt-4 text-sm leading-relaxed">{brief.summary}</p>

          <div className="mt-5 flex-1">
            <p className="text-foreground text-sm font-semibold">
              {brief.includesTitle}
            </p>
            <ul className="mt-3 grid gap-2">
              {brief.includes.map(item => (
                <li
                  key={item}
                  className="text-body flex items-start gap-2 text-sm"
                >
                  <Check
                    className="text-primary-400 mt-0.5 size-4 shrink-0"
                    aria-hidden
                  />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <a
            href={brief.cta.href}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              buttonVariants({ variant: 'outline', size: 'md' }),
              'border-primary-500/60 bg-surface/40 text-foreground hover:border-primary-500 hover:bg-primary-500/10 mt-6 h-11 w-full gap-2 text-sm font-semibold',
            )}
          >
            {brief.cta.label}
            <ExternalLink className="size-3.5 opacity-80" aria-hidden />
          </a>
          <p className="text-muted-foreground mt-2 text-center text-xs">
            {brief.ctaFootnote}
          </p>
        </div>

        {/* Meet the analyst */}
        <div className="border-border bg-background-alt/80 flex flex-col overflow-hidden rounded-2xl border">
          <div className="relative aspect-[4/5] w-full overflow-hidden sm:aspect-[3/4] lg:aspect-auto lg:min-h-[280px] lg:flex-1">
            {/* eslint-disable-next-line @next/next/no-img-element -- marketing portrait asset */}
            <img
              src={analyst.portraitSrc}
              alt={analyst.portraitAlt}
              className="absolute inset-0 size-full object-cover object-[center_20%]"
            />
            <div
              className="absolute inset-0 bg-gradient-to-t from-[#070d19] via-[#070d19]/55 to-transparent"
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

          <ul className="space-y-2.5 border-border/60 border-t p-5 sm:p-6">
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
    </LandingSection>
  );
}
