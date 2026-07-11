import { formatBriefDate } from '@/lib/briefs';
import { cn } from '@/lib/utils';
import type { SubscriberBrief } from '@/types/briefs';
import Link from 'next/link';
import type { FC } from 'react';

import { BriefCover } from './BriefCover';

export type RecentAdditionCardProps = {
  brief: SubscriberBrief;
  className?: string;
};

/** Compact horizontal brief used inside the "Recent Additions" strip. */
export const RecentAdditionCard: FC<RecentAdditionCardProps> = ({
  brief,
  className,
}) => (
  <Link
    href={brief.href}
    aria-label={`${brief.title} — risk score ${brief.riskScore}`}
    className={cn(
      'border-border bg-surface/30 hover:border-primary-500/40 focus-visible:ring-primary-500/40 group flex items-center gap-3 rounded-lg border p-2.5 transition-colors focus-visible:ring-2 focus-visible:outline-none',
      className,
    )}
  >
    {brief.featuredImage ? (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={brief.featuredImage}
        alt=""
        className="size-14 shrink-0 rounded-md object-cover"
      />
    ) : (
      <BriefCover
        theme={brief.coverTheme}
        iconSizeClassName="size-10"
        className="size-14 shrink-0 rounded-md"
      />
    )}
    <div className="min-w-0">
      <h4 className="text-foreground line-clamp-2 text-sm font-semibold leading-snug">
        {brief.title}
      </h4>
      <p className="text-muted mt-1 text-xs">
        <span className="text-danger font-semibold">Risk: {brief.riskScore}</span>
        <span className="mx-1.5" aria-hidden>
          •
        </span>
        {formatBriefDate(brief.date)}
      </p>
    </div>
  </Link>
);
