import { cn } from '@/lib/utils';
import type { AlertItem } from '@/types/alert';
import type { FC } from 'react';

import { AlertRow } from './AlertRow';

export type AlertTableProps = {
  alerts: AlertItem[];
  className?: string;
  alertsListReturnQuery?: string;
};

export const AlertTable: FC<AlertTableProps> = ({
  alerts,
  className,
  alertsListReturnQuery,
}) => (
  <div className={cn('flex flex-col gap-3 sm:gap-4', className)}>
    {alerts.length === 0 ? (
      <div className="text-muted py-10 text-center text-sm">
        No alerts match your filters.
      </div>
    ) : (
      alerts.map(alert => (
        <AlertRow
          key={alert.id}
          alert={alert}
          alertsListReturnQuery={alertsListReturnQuery}
        />
      ))
    )}
  </div>
);
