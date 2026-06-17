'use client';

import { RiskCountPill } from '@/components/ui/RiskCountPill';
import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import Link from 'next/link';
import { Children, type FC, type ReactNode, useId, useState } from 'react';

export type DashboardAlertGroupRiskTone = 'high' | 'medium' | 'low';

const riskToneStyles: Record<
  DashboardAlertGroupRiskTone,
  { link: string; viewAllLabel: string }
> = {
  high: {
    link: 'text-danger hover:text-danger-300',
    viewAllLabel: 'View All High Risk',
  },
  medium: {
    link: 'text-warning hover:text-warning-300',
    viewAllLabel: 'View All Medium Risk',
  },
  low: {
    link: 'text-success hover:text-success-300',
    viewAllLabel: 'View All Low Risk',
  },
};

const collapsibleBarTone: Record<DashboardAlertGroupRiskTone, string> = {
  high: 'border-border',
  medium: 'border-border',
  low: 'border-success/40',
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
  /** When true, list body is behind a toggle (e.g. low risk). */
  collapsible?: boolean;
  /** Initial collapsed state when `collapsible` is true. Defaults to `true`. */
  defaultCollapsed?: boolean;
  /** Shown on the toggle row while collapsed. */
  collapsedSummary?: string;
  /** Shown on the toggle row while expanded (optional). */
  expandedSummary?: string;
};

export const DashboardAlertGroup: FC<DashboardAlertGroupProps> = ({
  title,
  count,
  viewAllHref,
  riskTone,
  children,
  emptyMessage,
  className,
  collapsible = false,
  defaultCollapsed = true,
  collapsedSummary,
  expandedSummary,
}) => {
  const tone = riskToneStyles[riskTone];
  const listId = useId();
  const [collapsed, setCollapsed] = useState(
    collapsible ? defaultCollapsed : false,
  );

  const childCount = Children.count(children);
  const showEmpty = !collapsed && childCount === 0 && emptyMessage;

  const toggleRow = collapsible ? (
    <button
      type="button"
      id={`${listId}-toggle`}
      aria-expanded={!collapsed}
      aria-controls={listId}
      onClick={() => setCollapsed(c => !c)}
      className={cn(
        'cursor-pointer border-border hover:bg-surface/35 flex w-full items-center justify-between gap-3 rounded-md border px-4 py-3 text-left transition-colors',
        collapsibleBarTone[riskTone],
      )}
    >
      <span className="text-muted text-sm leading-snug">
        {collapsed
          ? (collapsedSummary ?? 'Tap to expand alerts in this section.')
          : (expandedSummary ?? 'Tap to collapse this section.')}
      </span>
      <ChevronDown
        className={cn(
          'text-muted-foreground size-5 shrink-0 transition-transform duration-200',
          !collapsed && 'rotate-180',
        )}
        aria-hidden
      />
    </button>
  ) : null;

  const listBody = (
    <div
      id={collapsible ? listId : undefined}
      className="flex flex-col gap-2"
      {...(collapsible
        ? { role: 'region' as const, 'aria-labelledby': `${listId}-toggle` }
        : {})}
    >
      {children}
      {showEmpty ? (
        <p className="border-border text-muted rounded-lg border border-dashed px-4 py-8 text-center text-sm">
          {emptyMessage}
        </p>
      ) : null}
    </div>
  );

  return (
    <section className={cn('flex flex-col gap-3', className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-heading text-foreground font-semibold tracking-tight sm:text-base">
            {title}
          </h2>
          <RiskCountPill variant={riskTone} count={count} />
        </div>
        <Link
          href={viewAllHref}
          className={cn('cursor-pointer text-xs font-semibold sm:text-sm', tone.link)}
        >
          {tone.viewAllLabel}
        </Link>
      </div>
      {collapsible ? (
        <>
          {toggleRow}
          {!collapsed ? listBody : null}
        </>
      ) : (
        listBody
      )}
    </section>
  );
};
