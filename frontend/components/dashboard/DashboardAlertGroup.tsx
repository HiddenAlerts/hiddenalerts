import { cn } from '@/lib/utils';
import Link from 'next/link';
import { Children, type FC, type ReactNode } from 'react';

export type DashboardAlertGroupRiskTone = 'high' | 'medium' | 'low';

const riskToneStyles: Record<
  DashboardAlertGroupRiskTone,
  { badge: string; link: string; viewAllLabel: string }
> = {
  high: {
    badge: 'bg-danger-muted text-danger',
    link: 'text-danger hover:text-danger-300',
    viewAllLabel: 'View All High Risk',
  },
  medium: {
    badge: 'bg-warning-muted text-warning',
    link: 'text-warning hover:text-warning-300',
    viewAllLabel: 'View All Medium Risk',
  },
  low: {
    badge: 'bg-success-muted text-success',
    link: 'text-success hover:text-success-300',
    viewAllLabel: 'View All Low Risk',
  },
};

export type DashboardAlertGroupProps = {
  title: string;
  count: number;
  viewAllHref: string;
  /** Drives count badge tint and “View All …” link label + color. */
  riskTone: DashboardAlertGroupRiskTone;
  children: ReactNode;
  /** Shown when there are no alert rows. */
  emptyMessage?: string;
  className?: string;
};

export const DashboardAlertGroup: FC<DashboardAlertGroupProps> = ({
  title,
  count,
  viewAllHref,
  riskTone,
  children,
  emptyMessage,
  className,
}) => {
  const tone = riskToneStyles[riskTone];

  return (
    <section className={cn('flex flex-col gap-3', className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-heading text-foreground font-semibold tracking-tight sm:text-base">
            {title}
          </h2>
          <span
            className={cn(
              'inline-flex min-h-6 min-w-6 items-center justify-center rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums',
              tone.badge,
            )}
          >
            {count}
          </span>
        </div>
        <Link
          href={viewAllHref}
          className={cn('text-xs font-semibold sm:text-sm', tone.link)}
        >
          {tone.viewAllLabel}
        </Link>
      </div>
      <div className="flex flex-col gap-2">
        {children}
        {Children.count(children) === 0 && emptyMessage ? (
          <p className="border-border text-muted rounded-lg border border-dashed px-4 py-8 text-center text-sm">
            {emptyMessage}
          </p>
        ) : null}
      </div>
    </section>
  );
};
