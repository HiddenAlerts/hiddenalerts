'use client';

import { BriefCard } from '@/components/briefs/BriefCard';
import { cn } from '@/lib/utils';
import type { SubscriberBrief } from '@/types/briefs';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

export type DashboardIntelligenceBriefsProps = {
  title?: string;
  subtitle?: string;
  briefs: SubscriberBrief[];
  viewAllHref: string;
  viewAllLabel?: string;
  bodyContent?: ReactNode;
  className?: string;
};

export const DashboardIntelligenceBriefs: FC<
  DashboardIntelligenceBriefsProps
> = ({
  title = 'Featured Intelligence Briefs',
  subtitle = 'In-depth analysis and insights on emerging threats and trends.',
  briefs,
  viewAllHref,
  viewAllLabel = 'View all briefs',
  bodyContent,
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

    {bodyContent ?? (
      briefs.length === 0 ? (
        <p className="text-muted border-border mt-5 rounded-lg border border-dashed px-4 py-8 text-center text-sm">
          No intelligence briefs available right now.
        </p>
      ) : (
        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 md:gap-4">
          {briefs.map(brief => (
            <BriefCard
              key={brief.id}
              brief={brief}
              imageClassName="aspect-[16/9]"
            />
          ))}
        </div>
      )
    )}
  </section>
);
