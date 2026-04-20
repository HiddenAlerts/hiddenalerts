import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

export type DashboardStatCardTone = 'danger' | 'warning' | 'muted' | 'primary';

const toneStyles: Record<
  DashboardStatCardTone,
  { top: string; value: string }
> = {
  danger: {
    top: 'border-t-danger',
    value: 'text-danger',
  },
  warning: {
    top: 'border-t-warning',
    value: 'text-warning',
  },
  muted: {
    top: 'border-t-border',
    value: 'text-muted',
  },
  primary: {
    top: 'border-t-primary-500',
    value: 'text-primary-400',
  },
};

export type DashboardStatCardProps = {
  label: string;
  value: number;
  tone?: DashboardStatCardTone;
  /** Optional footnote under the label */
  description?: ReactNode;
  className?: string;
};

export const DashboardStatCard: FC<DashboardStatCardProps> = ({
  label,
  value,
  tone = 'muted',
  description,
  className,
}) => {
  const styles = toneStyles[tone];
  return (
    <div
      className={cn(
        'border-border bg-background-alt rounded-lg border border-t-2 px-4 py-3 shadow-xs',
        styles.top,
        className,
      )}
    >
      <p
        className={cn(
          'font-heading text-2xl font-semibold tabular-nums tracking-tight',
          styles.value,
        )}
      >
        {value}
      </p>
      <p className="text-muted mt-1 text-xs font-medium tracking-wide uppercase">
        {label}
      </p>
      {description ? (
        <div className="text-muted mt-0.5 text-xs normal-case">{description}</div>
      ) : null}
    </div>
  );
};
