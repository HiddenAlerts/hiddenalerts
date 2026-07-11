import { formatBriefDate } from '@/lib/briefs';
import type { BriefLibraryStats } from '@/lib/briefs';
import { cn } from '@/lib/utils';
import type { SubscriberBrief } from '@/types/briefs';
import { AlertTriangle, FileText, ShieldAlert, Star } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

import { BriefStatCard } from './BriefStatCard';

export type BriefsStatsRowProps = {
  stats: BriefLibraryStats;
  featured?: SubscriberBrief;
  className?: string;
};

export const BriefsStatsRow: FC<BriefsStatsRowProps> = ({
  stats,
  featured,
  className,
}) => (
  <div
    className={cn(
      'border-border bg-background-alt grid grid-cols-2 items-center gap-x-0 gap-y-3 rounded-xl border p-3 md:grid-cols-3 xl:grid-cols-4',
      className,
    )}
  >
    <BriefStatCard
      icon={<FileText />}
      value={stats.total}
      label="Total Briefs"
      sublabel="Briefs in Library"
      tone="info"
      className="px-3"
    />
    <BriefStatCard
      icon={<ShieldAlert />}
      value={stats.critical}
      label="Critical Risk"
      sublabel="High Priority"
      tone="danger"
      className="border-border border-l px-3"
    />
    <BriefStatCard
      icon={<AlertTriangle />}
      value={stats.high}
      label="High Risk"
      sublabel="Monitor Closely"
      tone="warning"
      className="border-border px-3 md:border-l"
    />

    {featured ? (
      <Link
        href={featured.href}
        className="border-border bg-background-alt hover:border-primary-500/40 focus-visible:ring-primary-500/40 col-span-2 flex items-center gap-3 rounded-xl border p-4 transition-colors focus-visible:ring-2 focus-visible:outline-none md:col-span-3 xl:col-span-1"
        aria-label={`Featured intelligence brief: ${featured.title}`}
      >
        <span
          className="bg-primary-500/15 text-primary-500 inline-flex size-10 shrink-0 items-center justify-center rounded-lg"
          aria-hidden
        >
          <Star className="size-5" />
        </span>
        <div className="min-w-0">
          <p className="text-muted text-[0.65rem] font-semibold tracking-wide uppercase">
            Featured Intelligence Brief
          </p>
          <p className="text-foreground line-clamp-2 text-xs leading-snug font-semibold">
            {featured.title}
          </p>
          <p className="text-muted text-xs">{formatBriefDate(featured.date)}</p>
        </div>
      </Link>
    ) : null}
  </div>
);
