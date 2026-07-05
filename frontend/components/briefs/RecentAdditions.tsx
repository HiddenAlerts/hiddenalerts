import { cn } from '@/lib/utils';
import type { SubscriberBrief } from '@/types/briefs';
import { ArrowRight, Sparkles } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

import { RecentAdditionCard } from './RecentAdditionCard';

export type RecentAdditionsProps = {
  briefs: SubscriberBrief[];
  viewAllHref: string;
  className?: string;
};

export const RecentAdditions: FC<RecentAdditionsProps> = ({
  briefs,
  viewAllHref,
  className,
}) => {
  if (briefs.length === 0) return null;

  return (
    <section
      className={cn(
        'border-border bg-background-alt rounded-xl border p-4 sm:p-5',
        className,
      )}
      aria-labelledby="recent-additions-heading"
    >
      <div className="flex items-center justify-between gap-3">
        <h2
          id="recent-additions-heading"
          className="text-danger inline-flex items-center gap-1.5 text-xs font-bold tracking-wide uppercase"
        >
          <Sparkles className="size-4" aria-hidden />
          Recent Additions
        </h2>
        <Link
          href={viewAllHref}
          className="text-danger hover:text-danger-300 inline-flex shrink-0 cursor-pointer items-center gap-1 text-xs font-semibold whitespace-nowrap"
        >
          View All New
          <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {briefs.map(brief => (
          <RecentAdditionCard key={brief.id} brief={brief} />
        ))}
      </div>
    </section>
  );
};
