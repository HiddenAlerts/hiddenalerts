import { formatBriefDate } from '@/lib/briefs';
import { cn } from '@/lib/utils';
import type { SubscriberBrief } from '@/types/briefs';
import { Calendar, FileText, Lock, ShieldAlert, Tag } from 'lucide-react';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

import { BriefCover } from './BriefCover';
import { BriefRiskTag } from './BriefRiskTag';

type MetaItemProps = {
  icon: ReactNode;
  label: string;
  value: ReactNode;
};

const MetaItem: FC<MetaItemProps> = ({ icon, label, value }) => (
  <div className="min-w-0">
    <p className="text-muted/90 flex items-center gap-1.5 text-[0.65rem] font-semibold tracking-wide uppercase">
      <span className="[&_svg]:size-3.5" aria-hidden>
        {icon}
      </span>
      {label}
    </p>
    <div className="text-foreground mt-1 text-sm font-semibold">{value}</div>
  </div>
);

export type FeaturedBriefCardProps = {
  brief: SubscriberBrief;
  className?: string;
};

/** Large hero card highlighting the featured intelligence brief. */
export const FeaturedBriefCard: FC<FeaturedBriefCardProps> = ({
  brief,
  className,
}) => {
  const heroContent = (
    <>
      <div className="relative flex items-start justify-between gap-4">
        <p className="text-danger inline-flex items-center gap-1.5 text-xs font-bold tracking-wide uppercase">
          <ShieldAlert className="size-4" aria-hidden />
          Featured Intelligence Brief
        </p>
        {brief.confidential ? (
          <span className="border-danger/60 text-danger inline-flex items-center gap-1 rounded-sm border px-2 py-1 text-[0.65rem] font-bold tracking-widest uppercase">
            <Lock className="size-3" aria-hidden />
            Confidential
          </span>
        ) : null}
      </div>

      <Link
        href={brief.href}
        className="focus-visible:ring-primary-500/40 relative mt-4 block max-w-2xl focus-visible:ring-2 focus-visible:outline-none"
      >
        <h2
          id="featured-brief-heading"
          className="font-heading text-foreground text-xl font-bold tracking-tight sm:text-2xl lg:text-[1.7rem] lg:leading-tight"
        >
          {brief.title}
        </h2>
      </Link>
    </>
  );

  return (
    <section
      className={cn(
        'border-danger/40 bg-background-alt overflow-hidden rounded-xl border',
        className,
      )}
      aria-labelledby="featured-brief-heading"
    >
      {brief.featuredImage ? (
        <div className="relative overflow-hidden px-5 py-6 sm:px-7 sm:py-8">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={brief.featuredImage}
            alt=""
            className="absolute inset-0 size-full object-cover"
          />
          <div className="absolute inset-0 bg-black/55" aria-hidden />
          {heroContent}
        </div>
      ) : (
        <BriefCover
          theme={brief.coverTheme}
          iconSizeClassName="size-48"
          className="relative px-5 py-6 sm:px-7 sm:py-8"
        >
          {heroContent}
        </BriefCover>
      )}

      <div className="border-border grid grid-cols-2 gap-4 border-t px-5 py-4 sm:px-7 lg:grid-cols-4">
        <MetaItem
          icon={<ShieldAlert />}
          label="Risk Score"
          value={
            <span className="flex flex-wrap items-center gap-2">
              <span className="tabular-nums">{brief.riskScore}/100</span>
              <BriefRiskTag riskLabel={brief.riskLabel} />
            </span>
          }
        />
        <MetaItem icon={<Tag />} label="Category" value={brief.category} />
        <MetaItem
          icon={<Calendar />}
          label="Published"
          value={formatBriefDate(brief.date)}
        />
        <MetaItem
          icon={<FileText />}
          label="Source Count"
          value={<span className="tabular-nums">{brief.sourceCount}</span>}
        />
      </div>
    </section>
  );
};
