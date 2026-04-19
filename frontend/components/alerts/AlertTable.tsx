import { cn } from '@/lib/utils';
import type { AlertItem } from '@/types/alert';
import type { FC } from 'react';

import { AlertRow } from './AlertRow';

export type AlertTableProps = {
  alerts: AlertItem[];
  className?: string;
};

export const AlertTable: FC<AlertTableProps> = ({ alerts, className }) => (
  <div
    className={cn(
      'border-border bg-background-alt overflow-hidden rounded-lg border',
      className,
    )}
  >
    <div className="scrollbar-thin overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-left">
        <thead>
          <tr className="border-border bg-surface-muted/50 text-muted border-b text-xs font-medium tracking-wide uppercase">
            <th scope="col" className="px-4 py-3 lg:px-5">
              Alert
            </th>
            <th scope="col" className="px-4 py-3 lg:px-5">
              Source
            </th>
            <th
              scope="col"
              className="px-4 py-3 text-right lg:px-5"
            >
              Date / time
            </th>
          </tr>
        </thead>
        <tbody>
          {alerts.length === 0 ? (
            <tr>
              <td
                colSpan={3}
                className="text-muted px-4 py-10 text-center text-sm lg:px-5"
              >
                No alerts match your filters.
              </td>
            </tr>
          ) : (
            alerts.map((alert) => <AlertRow key={alert.id} alert={alert} />)
          )}
        </tbody>
      </table>
    </div>
  </div>
);
