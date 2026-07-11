import { formatBriefDate } from '@/lib/briefs';
import { cn } from '@/lib/utils';
import type { BriefRiskLabel, SubscriberBrief } from '@/types/briefs';
import { ArrowRight, FileText } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

import { BriefCover } from './BriefCover';
import { BriefRiskTag } from './BriefRiskTag';

const riskScoreTone: Record<BriefRiskLabel, string> = {
  Critical: 'text-danger',
  High: 'text-warning',
  Medium: 'text-warning',
  Low: 'text-success',
};

export type BriefCardProps = {
  brief: SubscriberBrief;
  className?: string;
};

/** Standard library grid card: themed cover, risk score, title, meta footer. */
export const BriefCard: FC<BriefCardProps> = ({ brief, className }) => (
  <Link
    href={brief.href}
    aria-label={`${brief.title} — risk score ${brief.riskScore} out of 100, ${brief.riskLabel} risk`}
    className={cn(
      'border-border bg-background-alt focus-visible:ring-primary-500/40 group relative flex flex-col overflow-hidden rounded-xl border transition-colors hover:border-primary-500/40 focus-visible:ring-2 focus-visible:outline-none',
      className,
    )}
  >
    <div className="relative aspect-[16/10] w-full overflow-hidden">
      {brief.featuredImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={brief.featuredImage}
          alt=""
          className="size-full object-cover"
        />
      ) : (
        <BriefCover theme={brief.coverTheme} className="size-full" />
      )}
      <div className="absolute inset-x-3 top-3 flex items-start justify-between gap-2">
        <BriefRiskTag riskLabel={brief.riskLabel} />
        <span className="rounded-sm bg-black/45 px-1.5 py-0.5 text-sm font-semibold text-white tabular-nums backdrop-blur-sm">
          {brief.riskScore}/100
        </span>
      </div>
    </div>

    <div className="flex flex-1 flex-col gap-3 p-4">
      <span
        className={cn('text-xs font-semibold tracking-wide uppercase', riskScoreTone[brief.riskLabel])}
      >
        {brief.category}
      </span>
      <h3 className="text-foreground line-clamp-3 text-sm font-semibold leading-snug">
        {brief.title}
      </h3>
      <div className="text-muted mt-auto flex flex-wrap items-center justify-between gap-x-2 gap-y-1 text-xs">
        <span className="whitespace-nowrap">{formatBriefDate(brief.date)}</span>
        <span className="inline-flex items-center gap-1 whitespace-nowrap">
          <FileText className="size-3.5" aria-hidden />
          Source Count: {brief.sourceCount}
        </span>
      </div>
    </div>

    <span
      className="text-danger group-hover:text-danger-300 pointer-events-none absolute right-4 bottom-4 opacity-0 transition-opacity group-hover:opacity-100"
      aria-hidden
    >
      <ArrowRight className="size-4" />
    </span>
  </Link>
);
