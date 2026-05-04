import { Button } from '@/components';
import { cn } from '@/lib/utils';
import { Bell, ChevronRight, RefreshCw } from 'lucide-react';
import type { FC, ReactNode } from 'react';

export type DashboardPageHeaderProps = {
  title: string;
  subtitle: string;
  statusLine: ReactNode;
  lastUpdatedLabel: string;
  onRefresh?: () => void;
  onViewAlerts?: () => void;
  className?: string;
};

export const DashboardPageHeader: FC<DashboardPageHeaderProps> = ({
  title,
  subtitle,
  statusLine,
  lastUpdatedLabel,
  onRefresh,
  onViewAlerts,
  className,
}) => (
  <div
    className={cn(
      'flex flex-col gap-4 border-border/80 border-b pb-6 lg:flex-row lg:items-start lg:justify-between',
      className,
    )}
  >
    <div className="min-w-0 space-y-2">
      <h1 className="font-heading text-foreground flex items-center gap-2.5 text-2xl font-semibold tracking-tight sm:text-[1.65rem]">
        <Bell className="text-danger size-7 shrink-0 sm:size-8" aria-hidden />
        <span>{title}</span>
      </h1>
      <p className="text-body max-w-2xl text-sm leading-relaxed sm:text-[0.95rem]">
        {subtitle}
      </p>
      <p className="text-muted text-sm">
        {statusLine}
        <span className="text-muted-foreground mx-1.5">•</span>
        <span className="text-muted">Last updated: {lastUpdatedLabel}</span>
      </p>
    </div>
    <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
      <Button
        type="button"
        size="sm"
        rightIcon={<ChevronRight className="size-4" aria-hidden />}
        className="border-white/25 bg-white text-primary-500 hover:bg-white/92 hover:text-primary-600 active:bg-white/85 border"
        onClick={onViewAlerts}
      >
        View Alerts
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        leftIcon={<RefreshCw className="size-4" aria-hidden />}
        className="border-border text-foreground hover:bg-surface/55 bg-transparent"
        onClick={onRefresh}
      >
        Refresh
      </Button>
    </div>
  </div>
);
