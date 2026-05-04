'use client';

import { Button } from '@/components';
import { cn } from '@/lib/utils';
import { ChevronRight, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

export type AlertsPageHeaderProps = {
  title: string;
  subtitle: string;
  lastUpdatedLabel: string | null;
  onRefresh: () => void;
  onEarlyAccess?: () => void;
  className?: string;
};

export const AlertsPageHeader: FC<AlertsPageHeaderProps> = ({
  title,
  subtitle,
  lastUpdatedLabel,
  onRefresh,
  onEarlyAccess,
  className,
}) => (
  <div
    className={cn(
      'border-border/80 flex flex-col gap-4 border-b pb-6 lg:flex-row lg:items-start lg:justify-between',
      className,
    )}
  >
    <div className="min-w-0 space-y-2">
      <nav aria-label="Breadcrumb" className="text-muted text-xs font-medium">
        <ol className="flex flex-wrap items-center gap-1.5">
          <li>
            <Link
              href="/dashboard"
              className="hover:text-foreground focus-visible:ring-primary-500 rounded transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none"
            >
              Dashboard
            </Link>
          </li>
          <li aria-hidden className="text-muted-foreground">
            <ChevronRight className="size-3.5" />
          </li>
          <li className="text-body">Alerts</li>
        </ol>
      </nav>
      <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight sm:text-[1.65rem]">
        {title}
      </h1>
      <p className="text-body max-w-2xl text-sm leading-relaxed sm:text-[0.95rem]">
        {subtitle}
      </p>
      {lastUpdatedLabel ? (
        <p className="text-muted text-sm tabular-nums">
          Last updated: {lastUpdatedLabel}
        </p>
      ) : null}
    </div>
    <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
      {onEarlyAccess ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="border-border text-foreground hover:bg-surface/55 bg-transparent"
          onClick={onEarlyAccess}
        >
          Get Early Access
        </Button>
      ) : null}
      <Button
        type="button"
        size="sm"
        leftIcon={<RefreshCw className="size-4" aria-hidden />}
        className="border-white/25 bg-white text-primary-500 hover:bg-white/92 hover:text-primary-600 active:bg-white/85 border"
        onClick={onRefresh}
      >
        Refresh
      </Button>
    </div>
  </div>
);
