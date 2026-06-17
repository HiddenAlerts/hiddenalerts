import { cn } from '@/lib/utils';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

export type DashboardSectionCardProps = {
  title: string;
  subtitle?: string;
  /** Optional link rendered at the top-right corner. */
  viewAllHref?: string;
  viewAllLabel?: string;
  /** Aria id linking the header heading to the section. */
  headingId?: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
};

/**
 * Reusable bordered surface used by lower dashboard sections (Alerts, Top
 * Alerts This Week, etc.). Provides consistent header + body padding with an
 * optional "View all …" link.
 */
export const DashboardSectionCard: FC<DashboardSectionCardProps> = ({
  title,
  subtitle,
  viewAllHref,
  viewAllLabel = 'View all',
  headingId,
  children,
  className,
  bodyClassName,
}) => (
  <section
    className={cn(
      'border-border bg-background-alt rounded-xl border p-4 sm:p-5 lg:p-6',
      className,
    )}
    aria-labelledby={headingId}
  >
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
      <div className="min-w-0 space-y-1">
        <h2
          id={headingId}
          className="font-heading text-foreground text-lg font-semibold tracking-tight sm:text-xl"
        >
          {title}
        </h2>
        {subtitle ? (
          <p className="text-muted max-w-2xl text-sm leading-relaxed">
            {subtitle}
          </p>
        ) : null}
      </div>
      {viewAllHref ? (
        <Link
          href={viewAllHref}
          className="text-danger hover:text-danger-300 inline-flex shrink-0 cursor-pointer items-center gap-1 text-sm font-semibold whitespace-nowrap"
        >
          {viewAllLabel}
          <ArrowRight className="size-4" aria-hidden />
        </Link>
      ) : null}
    </div>

    <div className={cn('mt-5', bodyClassName)}>{children}</div>
  </section>
);
