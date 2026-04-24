import Tag from '@/components/ui/Tag/Tag';
import { formatAlertDate } from '@/lib/formatAlertDate';
import { cn } from '@/lib/utils';
import type { AlertBadgeTone, AlertItem } from '@/types/alert';
import type { ComponentProps, FC } from 'react';

type TagType = NonNullable<ComponentProps<typeof Tag>['type']>;

const sourceTagType: Record<AlertBadgeTone, TagType> = {
  danger: 'danger',
  success: 'success',
  info: 'info',
  warning: 'warning',
};

export type AlertRowProps = {
  alert: AlertItem;
  className?: string;
};

export const AlertRow: FC<AlertRowProps> = ({ alert, className }) => (
  <tr
    className={cn(
      'border-border hover:bg-surface/60 border-b transition-colors last:border-b-0',
      className,
    )}
  >
    <td className="align-top px-4 py-4 lg:px-5">
      <div className="max-w-xl space-y-1">
        <p className="text-foreground font-semibold">{alert.title}</p>
        <p className="text-muted line-clamp-2 text-sm leading-relaxed">
          {alert.description}
        </p>
      </div>
    </td>
    <td className="align-top px-4 py-4 lg:px-5">
      <div className="flex justify-center lg:justify-start">
        <Tag
          title={alert.sourceLabel}
          type={sourceTagType[alert.badgeTone]}
          dot={false}
        />
      </div>
    </td>
    <td className="text-muted align-top whitespace-nowrap px-4 py-4 text-right text-sm lg:px-5">
      {formatAlertDate(alert.occurredAt)}
    </td>
  </tr>
);
