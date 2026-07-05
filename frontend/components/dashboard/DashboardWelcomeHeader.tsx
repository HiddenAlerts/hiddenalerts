'use client';

import { cn } from '@/lib/utils';
import { RefreshCw, Zap } from 'lucide-react';
import type { FC } from 'react';

export type DashboardWelcomeHeaderProps = {
  firstName: string;
  subtitle?: string;
  newAlertsSinceLastLogin?: number;
  lastUpdatedLabel: string;
  onRefresh?: () => void;
  className?: string;
};

export const DashboardWelcomeHeader: FC<DashboardWelcomeHeaderProps> = ({
  firstName,
  subtitle = 'Your fraud intelligence dashboard.',
  newAlertsSinceLastLogin,
  lastUpdatedLabel,
  onRefresh,
  className,
}) => {
  const showNewAlertsBadge =
    typeof newAlertsSinceLastLogin === 'number' && newAlertsSinceLastLogin > 0;

  return (
    <div
      className={cn(
        'flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between',
        className,
      )}
    >
      <div className="min-w-0 space-y-1">
        <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
          Welcome back, {firstName}.
        </h1>
        <p className="text-muted text-sm sm:text-base">{subtitle}</p>
      </div>

      <div className="flex flex-wrap items-center gap-3 sm:gap-5 lg:shrink-0">
        {showNewAlertsBadge ? (
          <span
            className="border-success/40 bg-success/10 text-foreground inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
            aria-label={`${newAlertsSinceLastLogin} new alerts since last login`}
          >
            <span
              className="bg-success/15 text-success inline-flex size-5 shrink-0 items-center justify-center rounded-sm"
              aria-hidden
            >
              <Zap className="size-3.5" strokeWidth={2.5} fill="currentColor" />
            </span>
            <span className="text-success font-semibold">
              +{newAlertsSinceLastLogin} new alerts
            </span>
            <span className="text-muted">since last login</span>
          </span>
        ) : null}

        <div className="text-muted inline-flex items-center gap-2 text-sm">
          <span>Updated {lastUpdatedLabel}</span>
          <button
            type="button"
            onClick={onRefresh}
            className="text-muted hover:text-foreground hover:bg-surface focus-visible:ring-primary-500/40 inline-flex size-7 cursor-pointer items-center justify-center rounded-md transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Refresh dashboard"
            disabled={!onRefresh}
          >
            <RefreshCw className="size-4" aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
};
