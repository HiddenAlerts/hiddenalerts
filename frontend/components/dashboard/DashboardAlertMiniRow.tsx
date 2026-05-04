import { alertDisplayedAtIso } from '@/lib/alertDisplay';
import { formatAlertDate } from '@/lib/formatAlertDate';
import { cn } from '@/lib/utils';
import type { AlertItem } from '@/types/alert';
import type { FC } from 'react';

export type DashboardAlertMiniRowProps = {
  alert: AlertItem;
  className?: string;
};

/** Compact table row for dashboard risk columns. */
export const DashboardAlertMiniRow: FC<DashboardAlertMiniRowProps> = ({
  alert,
  className,
}) => (
  <tr
    className={cn(
      'border-border hover:bg-surface/40 border-b transition-colors last:border-b-0',
      className,
    )}
  >
    <td className="max-w-0 px-3 py-2.5 align-top sm:px-4">
      <p className="text-foreground truncate text-sm font-medium">
        {alert.title}
      </p>
      <p className="text-muted mt-0.5 line-clamp-1 text-xs leading-snug">
        {alert.description}
      </p>
    </td>
    <td className="text-muted w-[1%] whitespace-nowrap px-3 py-2.5 text-right text-xs sm:px-4">
      {formatAlertDate(alertDisplayedAtIso(alert))}
    </td>
  </tr>
);
