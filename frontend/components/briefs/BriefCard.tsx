import { formatBriefDate, formatBriefRiskScore } from '@/lib/briefs';
import { cn } from '@/lib/utils';
import type { BriefRiskLabel, SubscriberBrief } from '@/types/briefs';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

import { BriefCover } from './BriefCover';
import { BriefRiskTag } from './BriefRiskTag';

const riskScoreTone: Record<BriefRiskLabel, string> = {
  Critical: 'text-danger',
  High: 'text-warning',
  Medium: 'text-warning',
  Low: 'text-success',
  Unknown: 'text-muted',
};

export type BriefCardProps = {
  brief: SubscriberBrief;
  className?: string;
  /** Override cover aspect (default `aspect-[16/9]`). */
  imageClassName?: string;
};

/** Standard library grid card: themed cover, risk score, title, meta footer. */
export const BriefCard: FC<BriefCardProps> = ({
  brief,
  className,
  imageClassName,
}) => (
  <Link
    href={brief.href}
    aria-label={`${brief.title} — risk score ${formatBriefRiskScore(brief.riskScore)}, ${brief.riskLabel} risk`}
    className={cn(
      'border-border bg-background-alt focus-visible:ring-primary-500/40 group relative flex h-full flex-col overflow-hidden rounded-xl border transition-colors hover:border-primary-500/40 focus-visible:ring-2 focus-visible:outline-none',
      className,
    )}
  >
    <div
      className={cn(
        'bg-surface-muted relative w-full overflow-hidden',
        imageClassName ?? 'aspect-[16/9]',
      )}
    >
      {brief.featuredImage ? (
        // object-contain: CMS covers are often tall infographics — cover crops
        // them into an unrecognizable (or wrong-looking) thumbnail.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={brief.featuredImage}
          alt=""
          className="bg-surface-muted size-full object-contain object-center"
        />
      ) : (
        <BriefCover theme={brief.coverTheme} className="size-full" />
      )}
      <div className="absolute inset-x-3 top-3 flex items-start justify-between gap-2">
        <BriefRiskTag riskLabel={brief.riskLabel} />
      </div>
    </div>

    <div className="flex flex-1 flex-col gap-2.5 p-3.5 sm:p-4">
      <span
        className={cn(
          'line-clamp-1 text-xs font-semibold tracking-wide uppercase',
          riskScoreTone[brief.riskLabel],
        )}
      >
        {brief.category}
      </span>
      <h3 className="text-foreground line-clamp-3 min-h-[3.75rem] text-sm leading-snug font-semibold">
        {brief.title}
      </h3>
      <div className="mt-auto flex items-center justify-between gap-3 pt-1">
        <div className="text-muted grid min-w-0 flex-1 grid-cols-[1fr_auto] items-center gap-x-2 text-xs">
          <span className="truncate whitespace-nowrap">
            {formatBriefDate(brief.date)}
          </span>
          <span
            className={cn(
              'font-semibold whitespace-nowrap tabular-nums',
              riskScoreTone[brief.riskLabel],
            )}
          >
            {formatBriefRiskScore(brief.riskScore)}
          </span>
        </div>
        <span
          className="text-danger group-hover:text-danger-300 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
          aria-hidden
        >
          <ArrowRight className="size-4" />
        </span>
      </div>
    </div>
  </Link>
);
