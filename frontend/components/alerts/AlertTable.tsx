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
      'bg-transparent p-0',
      className,
    )}
  >
    {alerts.length === 0 ? (
      <div className="text-muted py-10 text-center text-sm">
        No alerts match your filters.
      </div>
    ) : (
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
        {alerts.map(alert => (
          <AlertRow key={alert.id} alert={alert} />
        ))}
      </div>
    )}
  </div>
);
