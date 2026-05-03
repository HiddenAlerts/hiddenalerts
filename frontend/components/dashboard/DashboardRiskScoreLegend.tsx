import type { DashboardRiskLegendItem } from '@/data/dashboardRiskLegend';
import { cn } from '@/lib/utils';
import { Info } from 'lucide-react';
import type { FC } from 'react';

export type DashboardRiskScoreLegendProps = {
  items: DashboardRiskLegendItem[];
  infoTitle: string;
  infoDescription: string;
  className?: string;
};

export const DashboardRiskScoreLegend: FC<DashboardRiskScoreLegendProps> = ({
  items,
  infoTitle,
  infoDescription,
  className,
}) => (
  <div
    className={cn(
      'border-border bg-surface/45 flex flex-col gap-4 rounded-lg border p-4 sm:p-5 lg:flex-row lg:items-stretch lg:gap-6',
      className,
    )}
  >
    <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-3 sm:gap-4">
      {items.map(item => (
        <div key={item.id} className="flex min-w-0 gap-2.5">
          <span
            className={cn('mt-1.5 size-3 shrink-0 rounded-full', item.dotClass)}
            aria-hidden
          />
          <div className="min-w-0">
            <p className="text-foreground text-sm leading-snug font-semibold">
              {item.label}
            </p>
            <p className="text-muted mt-1 text-xs leading-relaxed">
              {item.description}
            </p>
          </div>
        </div>
      ))}
    </div>
    <div className="border-border flex gap-2.5 border-t pt-3 lg:w-[min(100%,280px)] lg:shrink-0 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-5">
      <Info className="text-info mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0">
        <p className="text-foreground text-sm font-semibold">{infoTitle}</p>
        <p className="text-muted mt-1 text-xs leading-relaxed">
          {infoDescription}
        </p>
      </div>
    </div>
  </div>
);
