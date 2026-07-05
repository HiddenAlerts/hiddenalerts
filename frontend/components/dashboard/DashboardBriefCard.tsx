import type { DashboardBriefItem } from '@/data/dashboardBriefs';
import { cn } from '@/lib/utils';
import { ArrowRight, Globe, Landmark, Lock, Ship } from 'lucide-react';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

const coverGradient: Record<DashboardBriefItem['coverTheme'], string> = {
  'cyber-network':
    'bg-[radial-gradient(circle_at_30%_30%,rgba(238,68,66,0.20),transparent_60%),linear-gradient(135deg,#0b1c3a,#0a1426_55%,#101a2e)]',
  capitol:
    'bg-[radial-gradient(circle_at_60%_40%,rgba(79,140,255,0.25),transparent_60%),linear-gradient(135deg,#142d52,#0e1f3a_60%,#091428)]',
  'credit-lock':
    'bg-[radial-gradient(circle_at_70%_40%,rgba(99,180,255,0.22),transparent_55%),linear-gradient(135deg,#0c1c34,#0a1426_55%,#080f1d)]',
  'shipping-port':
    'bg-[radial-gradient(circle_at_25%_30%,rgba(255,178,71,0.18),transparent_55%),linear-gradient(135deg,#0d1f37,#0a1422_55%,#0c1424)]',
};

const coverIconForTheme: Record<
  DashboardBriefItem['coverTheme'],
  ReactNode
> = {
  'cyber-network': (
    <Globe
      className="size-32 opacity-15"
      strokeWidth={1}
      aria-hidden
    />
  ),
  capitol: (
    <Landmark
      className="size-32 opacity-15"
      strokeWidth={1}
      aria-hidden
    />
  ),
  'credit-lock': (
    <Lock
      className="size-28 opacity-15"
      strokeWidth={1}
      aria-hidden
    />
  ),
  'shipping-port': (
    <Ship
      className="size-32 opacity-15"
      strokeWidth={1}
      aria-hidden
    />
  ),
};

const riskBadgeTone: Record<
  DashboardBriefItem['riskLabel'],
  string
> = {
  Critical: 'text-danger',
  High: 'text-warning',
  Medium: 'text-warning',
  Low: 'text-success',
};

const arrowTone: Record<DashboardBriefItem['riskLabel'], string> = {
  Critical: 'text-danger group-hover:text-danger-300',
  High: 'text-warning group-hover:text-warning-300',
  Medium: 'text-warning group-hover:text-warning-300',
  Low: 'text-success group-hover:text-success-300',
};

function formatBriefDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

export type DashboardBriefCardProps = {
  brief: DashboardBriefItem;
  className?: string;
};

export const DashboardBriefCard: FC<DashboardBriefCardProps> = ({
  brief,
  className,
}) => {
  return (
    <Link
      href={brief.href}
      className={cn(
        'border-border bg-background-alt focus-visible:ring-primary-500/40 group relative flex flex-col overflow-hidden rounded-xl border transition-colors hover:border-primary-500/40 focus-visible:ring-2 focus-visible:outline-none',
        className,
      )}
      aria-label={`${brief.title} — risk score ${brief.riskScore} out of 100, ${brief.riskLabel} risk`}
    >
      <div
        className={cn(
          'relative aspect-[16/10] w-full overflow-hidden',
          coverGradient[brief.coverTheme],
        )}
      >
        <div className="absolute inset-0 flex items-center justify-center text-white">
          {coverIconForTheme[brief.coverTheme]}
        </div>

        <div className="absolute top-3 left-3 flex flex-col gap-0.5">
          <span className="text-base font-semibold text-white tabular-nums sm:text-lg">
            {brief.riskScore}/100
          </span>
          <span
            className={cn(
              'text-sm font-semibold tracking-tight',
              riskBadgeTone[brief.riskLabel],
            )}
          >
            {brief.riskLabel}
          </span>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <h3 className="text-foreground line-clamp-3 text-sm font-semibold leading-snug sm:text-base">
          {brief.title}
        </h3>
        <div className="mt-auto flex items-end justify-between gap-2">
          <div className="min-w-0 space-y-0.5">
            <p className="text-muted truncate text-xs sm:text-sm">
              {brief.category}
            </p>
            <p className="text-muted text-xs sm:text-sm">
              {formatBriefDate(brief.date)}
            </p>
          </div>
          <ArrowRight
            className={cn(
              'size-5 shrink-0 transition-colors',
              arrowTone[brief.riskLabel],
            )}
            aria-hidden
          />
        </div>
      </div>
    </Link>
  );
};
