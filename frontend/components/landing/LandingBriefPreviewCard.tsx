import { INTELLIGENCE_BRIEF_PREVIEW } from '@/data/landing';
import { Check, ExternalLink } from 'lucide-react';

/**
 * Center column — Intelligence Brief Preview (approved final mockup).
 * Text-first: eyebrow + solid risk badge, title, timestamp, summary,
 * two-column includes list, ghost CTA. No cover thumbnail.
 */
export function LandingBriefPreviewCard() {
  const brief = INTELLIGENCE_BRIEF_PREVIEW;

  return (
    <article
      id="intelligence-brief"
      className="border-border bg-background-alt/80 flex h-full scroll-mt-24 flex-col rounded-xl border p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <h2 className="text-primary-500 text-[0.7rem] font-bold tracking-[0.16em] uppercase">
          {brief.eyebrow}
        </h2>
        <span className="bg-primary-500 inline-flex shrink-0 items-center rounded px-2.5 py-1 text-[0.7rem] font-semibold text-white tabular-nums">
          Risk Score: {brief.score}/100
        </span>
      </div>

      <h3 className="text-foreground mt-4 text-[1.15rem] leading-snug font-bold tracking-tight text-balance sm:text-xl">
        {brief.title}
      </h3>

      <p className="text-muted-foreground mt-2.5 text-xs sm:text-[0.8125rem]">
        {brief.publishedLabel}
      </p>

      <p className="text-muted-foreground mt-4 text-sm leading-relaxed">
        {brief.summary}
      </p>

      <div className="mt-5 flex-1">
        <p className="text-muted-foreground text-sm">{brief.includesLabel}</p>
        <div className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2.5 sm:grid-cols-2">
          <ul className="space-y-2.5">
            {brief.includesLeft.map(item => (
              <IncludeItem key={item} label={item} />
            ))}
          </ul>
          <ul className="space-y-2.5">
            {brief.includesRight.map(item => (
              <IncludeItem key={item} label={item} />
            ))}
          </ul>
        </div>
      </div>

      <a
        href={brief.cta.href}
        target="_blank"
        rel="noopener noreferrer"
        className="border-foreground/35 text-foreground hover:border-foreground/55 hover:bg-foreground/5 mt-6 inline-flex h-11 w-full items-center justify-center gap-2 rounded-md border bg-transparent px-4 text-sm font-semibold transition-colors"
      >
        <span className="truncate">{brief.cta.label}</span>
        <ExternalLink className="size-3.5 shrink-0 opacity-90" aria-hidden />
      </a>
    </article>
  );
}

function IncludeItem({ label }: { label: string }) {
  return (
    <li className="text-foreground flex items-start gap-2 text-sm">
      <Check
        className="text-primary-500 mt-0.5 size-4 shrink-0"
        strokeWidth={2.5}
        aria-hidden
      />
      <span>{label}</span>
    </li>
  );
}
