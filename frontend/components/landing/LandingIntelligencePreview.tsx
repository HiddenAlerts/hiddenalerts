import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Check, Lock } from 'lucide-react';
import Link from 'next/link';

import {
  INTELLIGENCE_BRIEF_PREVIEW,
  LIVE_ALERTS,
  LIVE_ALERTS_PANEL,
} from '@/data/landing';

import { LandingLiveAlertRow } from './LandingLiveAlertRow';
import { LandingSection } from './LandingSection';

export function LandingIntelligencePreview() {
  const brief = INTELLIGENCE_BRIEF_PREVIEW;

  return (
    <LandingSection
      id="sample-brief"
      ariaLabelledby="sample-brief-heading"
      className="border-border-subtle border-t"
    >
      <div className="grid gap-6 lg:grid-cols-2 lg:gap-8">
        {/* Live alerts panel */}
        <div className="border-border bg-background-alt rounded-xl border p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <h2
              id="sample-brief-heading"
              className="font-heading text-foreground text-lg font-semibold tracking-tight sm:text-xl"
            >
              {LIVE_ALERTS_PANEL.title}
            </h2>
            <Link
              href={LIVE_ALERTS_PANEL.viewAllHref}
              className="text-primary-400 hover:text-primary-300 shrink-0 text-sm font-medium transition-colors"
            >
              {LIVE_ALERTS_PANEL.viewAllLabel} →
            </Link>
          </div>

          <div className="mt-2">
            {LIVE_ALERTS.map(alert => (
              <LandingLiveAlertRow key={alert.rank} alert={alert} />
            ))}
          </div>

          <p className="text-muted-foreground mt-4 text-xs">
            {LIVE_ALERTS_PANEL.footnote}
          </p>
        </div>

        {/* Intelligence brief preview */}
        <div className="border-border bg-background-alt rounded-xl border p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-primary-400 text-xs font-semibold tracking-[0.14em] uppercase">
              {brief.eyebrow}
            </span>
            <span className="border-danger/40 bg-danger-muted text-danger rounded-md border px-2.5 py-1 text-xs font-semibold">
              Risk Score: {brief.score}/100
            </span>
          </div>

          <h3 className="text-foreground mt-4 text-lg leading-snug font-semibold sm:text-xl">
            {brief.title}
          </h3>
          <p className="text-muted-foreground mt-2 text-xs">{brief.date}</p>

          <p className="text-body mt-4 text-sm leading-relaxed">{brief.summary}</p>

          <div className="mt-6">
            <p className="text-foreground text-sm font-semibold">
              {brief.includesTitle}
            </p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
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

          <p className="text-muted mt-5 text-xs leading-relaxed">
            <span className="text-primary-400 font-semibold">*</span> {brief.note}
          </p>

          <Link
            href={brief.cta.href}
            className={cn(
              buttonVariants({ variant: 'default', size: 'md' }),
              'mt-5 h-12 w-full gap-2 text-sm font-semibold sm:text-base',
            )}
          >
            <Lock className="size-4" aria-hidden />
            {brief.cta.label}
          </Link>
          <p className="text-muted-foreground mt-2 text-center text-xs">
            {brief.ctaFootnote}
          </p>
        </div>
      </div>
    </LandingSection>
  );
}
