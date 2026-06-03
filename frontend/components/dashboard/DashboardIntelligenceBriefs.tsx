import type { DashboardBriefItem } from '@/data/dashboardBriefs';
import { cn } from '@/lib/utils';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

import { DashboardBriefCard } from './DashboardBriefCard';

export type DashboardIntelligenceBriefsProps = {
  title?: string;
  subtitle?: string;
  briefs: DashboardBriefItem[];
  viewAllHref: string;
  viewAllLabel?: string;
  className?: string;
};

export const DashboardIntelligenceBriefs: FC<
  DashboardIntelligenceBriefsProps
> = ({
  title = 'Intelligence Briefs',
  subtitle = 'In-depth analysis and insights on emerging threats and trends.',
  briefs,
  viewAllHref,
  viewAllLabel = 'View all briefs',
  className,
}) => (
  <section
    className={cn(
      'border-border bg-background-alt rounded-xl border p-4 sm:p-5 lg:p-6',
      className,
    )}
    aria-labelledby="dashboard-intelligence-briefs-heading"
  >
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
      <div className="min-w-0 space-y-1">
        <h2
          id="dashboard-intelligence-briefs-heading"
          className="font-heading text-foreground text-lg font-semibold tracking-tight sm:text-xl"
        >
          {title}
        </h2>
        <p className="text-muted max-w-2xl text-sm leading-relaxed">
          {subtitle}
        </p>
      </div>
      <Link
        href={viewAllHref}
        className="text-danger hover:text-danger-300 inline-flex shrink-0 cursor-pointer items-center gap-1 text-sm font-semibold whitespace-nowrap"
      >
        {viewAllLabel}
        <ArrowRight className="size-4" aria-hidden />
      </Link>
    </div>

    {briefs.length === 0 ? (
      <p className="text-muted border-border mt-5 rounded-lg border border-dashed px-4 py-8 text-center text-sm">
        No intelligence briefs available right now.
      </p>
    ) : (
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:gap-4">
        {briefs.map(brief => (
          <DashboardBriefCard key={brief.id} brief={brief} />
        ))}
      </div>
    )}
  </section>
);
