import { cn } from '@/lib/utils';
import type { AlertItem } from '@/types/alert';
import type { FC } from 'react';

import { DashboardAlertMiniRow } from './DashboardAlertMiniRow';

export type DashboardRiskTableProps = {
  title: string;
  count: number;
  alerts: AlertItem[];
  emptyMessage: string;
  className?: string;
};

export const DashboardRiskTable: FC<DashboardRiskTableProps> = ({
  title,
  count,
  alerts,
  emptyMessage,
  className,
}) => (
  <section className={cn('flex min-h-0 flex-col gap-2', className)}>
    <div className="flex items-baseline justify-between gap-2">
      <h2 className="font-heading text-foreground text-sm font-semibold tracking-tight">
        {title}
      </h2>
      <span className="text-muted tabular-nums text-xs font-medium">{count}</span>
    </div>
    <div className="border-border bg-background-alt flex min-h-[120px] flex-1 overflow-hidden rounded-lg border">
      <div className="scrollbar-thin w-full overflow-x-auto">
        <table className="w-full min-w-[280px] border-collapse text-left">
          <tbody>
            {alerts.length === 0 ? (
              <tr>
                <td
                  colSpan={2}
                  className="text-muted px-3 py-8 text-center text-sm sm:px-4"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              alerts.map((alert) => (
                <DashboardAlertMiniRow key={alert.id} alert={alert} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  </section>
);
