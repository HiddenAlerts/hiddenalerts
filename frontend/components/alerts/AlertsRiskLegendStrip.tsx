'use client';

import type { DashboardRiskLegendItem } from '@/data/dashboardRiskLegend';
import { cn } from '@/lib/utils';
import type { FC } from 'react';

export type AlertsRiskLegendStripProps = {
  items: readonly DashboardRiskLegendItem[];
  className?: string;
};

export const AlertsRiskLegendStrip: FC<AlertsRiskLegendStripProps> = ({
  items,
  className,
}) => (
  <div
    className={cn(
      'border-border bg-surface/25 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border px-4 py-3',
      className,
    )}
    role="list"
  >
    {items.map(item => (
      <div
        key={item.id}
        className="flex min-w-0 items-center gap-2"
        role="listitem"
      >
        <span
          className={cn('size-2.5 shrink-0 rounded-full', item.dotClass)}
          aria-hidden
        />
        <span className="text-foreground text-sm font-medium">{item.label}</span>
      </div>
    ))}
  </div>
);
