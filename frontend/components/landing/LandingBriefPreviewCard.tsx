import { buttonVariants } from '@/components/ui/button';
import { INTELLIGENCE_BRIEF_PREVIEW } from '@/data/landing';
import { cn } from '@/lib/utils';
import {
  ArrowRight,
  CalendarDays,
  Clock3,
  Crosshair,
  FileText,
  Shield,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';
import type { ReactNode } from 'react';

/**
 * Full-width Intelligence Brief Preview — matches Ken’s landing mockup.
 * Alerts / Analyst cards are unchanged siblings in LandingIntelligencePreview.
 */
export function LandingBriefPreviewCard() {
  const brief = INTELLIGENCE_BRIEF_PREVIEW;

  return (
    <div id="intelligence-brief" className="scroll-mt-24">
      {/* Section label */}
      <div className="mb-3 flex items-center gap-3">
        <Crosshair className="text-primary-500 size-4 shrink-0" aria-hidden />
        <h2 className="text-primary-500 text-xs font-bold tracking-[0.18em] uppercase">
          {brief.eyebrow}
        </h2>
        <span className="bg-primary-500 h-px min-w-8 flex-1" aria-hidden />
      </div>

      <article className="border-border bg-background-alt overflow-hidden rounded-2xl border">
        {/* Cover + risk score overlay */}
        <div className="relative aspect-[16/9] w-full sm:aspect-[2.2/1]">
          {/* eslint-disable-next-line @next/next/no-img-element -- marketing cover asset */}
          <img
            src={brief.coverSrc}
            alt={brief.coverAlt}
            className="absolute inset-0 size-full object-cover object-center"
          />
          <div
            className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent opacity-80"
            aria-hidden
          />

          <div className="border-primary-500/80 bg-background/85 absolute top-3 right-3 rounded-lg border-2 px-3 py-2.5 backdrop-blur-sm sm:top-4 sm:right-4 sm:px-4 sm:py-3">
            <p className="text-muted text-[0.65rem] font-semibold tracking-[0.14em] uppercase">
              Risk Score
            </p>
            <p className="text-foreground mt-0.5 text-xl font-bold tabular-nums sm:text-2xl">
              {brief.score}{' '}
              <span className="text-muted text-sm font-semibold">/ 100</span>
            </p>
            <span className="bg-primary-500 text-foreground mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[0.65rem] font-bold tracking-wide uppercase">
              <TriangleAlert className="size-3" aria-hidden />
              {brief.riskLevel}
            </span>
          </div>
        </div>

        {/* Body: summary + metadata */}
        <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[1fr_200px] lg:gap-6 lg:p-6">
          <div className="min-w-0">
            <p className="text-primary-400 flex items-center gap-2 text-xs font-semibold tracking-[0.12em] uppercase">
              <Shield className="size-3.5 shrink-0" aria-hidden />
              {brief.categories}
            </p>

            <h3 className="font-heading text-foreground mt-2.5 text-xl leading-snug font-bold tracking-tight text-balance sm:text-2xl">
              {brief.title}
            </h3>
            <span
              className="bg-primary-500 mt-2.5 block h-0.5 w-12"
              aria-hidden
            />

            {/* Executive Summary — tighter gap before the supporting callout */}
            <p className="text-body mt-2.5 text-sm leading-relaxed sm:text-[0.95rem]">
              {brief.summary}
            </p>

            <div className="border-border/70 bg-surface/50 mt-3 flex items-start gap-3 rounded-lg border px-3.5 py-3">
              <span className="bg-primary-500/15 text-primary-400 flex size-8 shrink-0 items-center justify-center rounded-full">
                <Crosshair className="size-3.5" aria-hidden />
              </span>
              <p className="text-body text-sm leading-relaxed">
                {brief.highlightLead}{' '}
                <span className="text-primary-400 font-semibold">
                  {brief.highlightBrand}
                </span>{' '}
                {brief.highlightTrail}
              </p>
            </div>

            {/* CTA sits under the copy column — not stretched across the full card */}
            <a
              href={brief.cta.href}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                buttonVariants({ variant: 'default', size: 'md' }),
                'mt-5 inline-flex h-11 w-full gap-2.5 px-5 text-sm font-semibold tracking-wide sm:w-fit',
              )}
            >
              <FileText className="size-4 shrink-0 opacity-90" aria-hidden />
              <span className="truncate">{brief.cta.label}</span>
              <ArrowRight className="size-4 shrink-0" aria-hidden />
            </a>
          </div>

          <dl className="border-border/60 divide-border/60 flex flex-col divide-y border-t lg:border-t-0">
            <MetaRow
              icon={<CalendarDays className="size-4" aria-hidden />}
              label="Published"
              value={brief.publishedLabel}
            />
            <MetaRow
              icon={<FileText className="size-4" aria-hidden />}
              label="Source Count"
              value={brief.sourceCount}
            />
            <MetaRow
              icon={<ShieldAlert className="size-4" aria-hidden />}
              label="Risk Level"
              value={brief.riskLevel}
            />
            <MetaRow
              icon={<Clock3 className="size-4" aria-hidden />}
              label="Time Horizon"
              value={brief.timeHorizon}
            />
          </dl>
        </div>
      </article>

      <p className="text-muted-foreground mt-3 flex items-center justify-center gap-2 text-center text-xs sm:text-sm">
        <ShieldCheck className="size-3.5 shrink-0 opacity-80" aria-hidden />
        {brief.footer}
      </p>
    </div>
  );
}

function MetaRow({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3 py-3 first:pt-0 last:pb-0 lg:py-3.5">
      <span className="text-primary-500 mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0">
        <dt className="text-muted-foreground text-[0.65rem] font-semibold tracking-[0.14em] uppercase">
          {label}
        </dt>
        <dd className="text-foreground mt-0.5 text-sm font-semibold">{value}</dd>
      </div>
    </div>
  );
}
