import type {
  DashboardRecentBrief,
  DashboardRecentBriefIcon,
  DashboardRecentBriefRiskLabel,
} from '@/data/dashboardRecentBriefs';
import { cn } from '@/lib/utils';
import {
  ArrowRight,
  ChevronRight,
  FileText,
  Landmark,
  Package,
  Phone,
} from 'lucide-react';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

const iconForType: Record<DashboardRecentBriefIcon, ReactNode> = {
  document: <FileText className="size-5" strokeWidth={1.75} aria-hidden />,
  phone: <Phone className="size-5" strokeWidth={1.75} aria-hidden />,
  package: <Package className="size-5" strokeWidth={1.75} aria-hidden />,
  landmark: <Landmark className="size-5" strokeWidth={1.75} aria-hidden />,
};

const riskColor: Record<DashboardRecentBriefRiskLabel, string> = {
  Critical: 'text-danger',
  High: 'text-warning',
  Medium: 'text-warning',
  Low: 'text-success',
};

function formatBriefDate(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { date: iso, time: '' };
  const date = d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const time = d.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC',
  });
  return { date, time: `${time} UTC` };
}

export type DashboardRecentBriefsTableProps = {
  title?: string;
  subtitle?: string;
  briefs: DashboardRecentBrief[];
  viewAllHref: string;
  viewAllLabel?: string;
  className?: string;
};

export const DashboardRecentBriefsTable: FC<
  DashboardRecentBriefsTableProps
> = ({
  title = 'Recent Intelligence Briefs',
  subtitle = 'Your recently viewed and saved briefs.',
  briefs,
  viewAllHref,
  viewAllLabel = 'View all briefs',
  className,
}) => (
  <section
    className={cn(
      'border-border bg-background-alt overflow-hidden rounded-xl border',
      className,
    )}
    aria-labelledby="dashboard-recent-briefs-heading"
  >
    <div className="flex flex-col gap-3 px-4 pt-4 pb-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6 sm:px-5 sm:pt-5 lg:px-6 lg:pt-6">
      <div className="min-w-0 space-y-1">
        <h2
          id="dashboard-recent-briefs-heading"
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
      <p className="text-muted border-border border-t px-4 py-8 text-center text-sm sm:px-5 lg:px-6">
        No recent briefs to display.
      </p>
    ) : (
      <>
        <div
          className="border-border-subtle text-muted hidden border-t border-b px-4 py-2.5 text-xs font-medium uppercase tracking-wide sm:px-5 lg:grid lg:grid-cols-[minmax(0,1fr)_140px_180px_24px] lg:gap-4 lg:px-6"
          aria-hidden
        >
          <span>Title</span>
          <span>Risk Score</span>
          <span>Last Updated</span>
          <span />
        </div>

        <ul
          className="divide-border-subtle border-border-subtle divide-y border-t lg:border-t-0"
          role="list"
        >
          {briefs.map(brief => {
            const { date, time } = formatBriefDate(brief.lastUpdatedIso);
            return (
              <li key={brief.id}>
                <Link
                  href={brief.href}
                  className="hover:bg-surface/40 focus-visible:ring-primary-500/40 group flex items-center gap-3 px-4 py-3.5 transition-colors focus-visible:ring-2 focus-visible:outline-none sm:px-5 sm:py-4 lg:grid lg:grid-cols-[minmax(0,1fr)_140px_180px_24px] lg:gap-4 lg:px-6"
                  aria-label={`Open brief: ${brief.title}, ${brief.riskScore} out of 100, ${brief.riskLabel} risk`}
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3 sm:gap-4">
                    <span
                      className="bg-danger/15 text-danger inline-flex size-9 shrink-0 items-center justify-center rounded-md sm:size-10"
                      aria-hidden
                    >
                      {iconForType[brief.iconType]}
                    </span>
                    <div className="min-w-0">
                      <p className="text-foreground line-clamp-2 text-sm font-semibold leading-snug sm:text-[0.95rem]">
                        {brief.title}
                      </p>
                      <p className="text-muted mt-0.5 truncate text-xs sm:text-sm">
                        <span>{brief.category}</span>
                        <span
                          className="text-muted-foreground/60 mx-1.5"
                          aria-hidden
                        >
                          •
                        </span>
                        <span>{brief.briefType}</span>
                      </p>
                    </div>
                  </div>

                  <div className="hidden flex-col leading-tight lg:flex">
                    <span
                      className={cn(
                        'text-base font-semibold tabular-nums',
                        riskColor[brief.riskLabel],
                      )}
                    >
                      {brief.riskScore}/100
                    </span>
                    <span
                      className={cn(
                        'text-sm font-medium',
                        riskColor[brief.riskLabel],
                      )}
                    >
                      {brief.riskLabel}
                    </span>
                  </div>

                  <div className="hidden flex-col leading-tight lg:flex">
                    <span className="text-foreground text-sm">{date}</span>
                    <span className="text-muted text-xs sm:text-sm">
                      {time}
                    </span>
                  </div>

                  <div className="hidden items-center justify-end lg:flex">
                    <ChevronRight
                      className="text-danger group-hover:text-danger-300 size-5 transition-colors"
                      aria-hidden
                    />
                  </div>

                  <div className="ml-auto flex shrink-0 items-end gap-3 lg:hidden">
                    <div className="flex flex-col items-end leading-tight">
                      <span
                        className={cn(
                          'text-sm font-semibold tabular-nums',
                          riskColor[brief.riskLabel],
                        )}
                      >
                        {brief.riskScore}/100
                      </span>
                      <span
                        className={cn(
                          'text-xs font-medium',
                          riskColor[brief.riskLabel],
                        )}
                      >
                        {brief.riskLabel}
                      </span>
                      <span className="text-muted mt-1 text-[0.7rem]">
                        {date}
                      </span>
                    </div>
                    <ChevronRight
                      className="text-danger size-5"
                      aria-hidden
                    />
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      </>
    )}
  </section>
);
