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
        'bg-surface-muted relative w-full shrink-0 overflow-hidden',
        imageClassName ?? 'aspect-[16/9]',
      )}
    >
      {brief.featuredImage ? (
        // object-cover in a 16:9 frame: standard 1200×675 thumbnails fill the
        // area; matching aspect ratios are not cropped.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={brief.featuredImage}
          alt=""
          className="bg-surface-muted size-full object-cover object-center"
        />
      ) : (
        <BriefCover theme={brief.coverTheme} className="size-full" />
      )}
      <div className="absolute inset-x-3 top-3 flex items-start justify-between gap-2">
        <BriefRiskTag riskLabel={brief.riskLabel} />
      </div>
    </div>

    {/* Fixed category + title slots keep meta/footer aligned across the grid. */}
    <div className="flex min-h-0 flex-1 flex-col p-3.5 sm:p-4">
      <span
        className={cn(
          'mb-2.5 block h-4 truncate text-xs leading-4 font-semibold tracking-wide uppercase',
          riskScoreTone[brief.riskLabel],
        )}
      >
        {brief.category || '\u00a0'}
      </span>
      <h3 className="text-foreground line-clamp-3 h-[3.75rem] shrink-0 text-sm leading-5 font-semibold">
        {brief.title}
      </h3>
      <div className="mt-auto flex shrink-0 items-center justify-between gap-3 pt-2.5">
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
