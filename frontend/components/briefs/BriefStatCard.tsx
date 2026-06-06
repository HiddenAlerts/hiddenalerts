import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

export type BriefStatTone = 'danger' | 'warning' | 'success' | 'info' | 'muted';

const toneIcon: Record<BriefStatTone, string> = {
  danger: 'bg-danger/15 text-danger',
  warning: 'bg-warning/15 text-warning',
  success: 'bg-success/15 text-success',
  info: 'bg-info/15 text-info',
  muted: 'bg-surface text-body',
};

const toneValue: Record<BriefStatTone, string> = {
  danger: 'text-danger',
  warning: 'text-warning',
  success: 'text-success',
  info: 'text-info',
  muted: 'text-foreground',
};

export type BriefStatCardProps = {
  icon: ReactNode;
  value: ReactNode;
  label: string;
  sublabel?: string;
  tone?: BriefStatTone;
  className?: string;
};

export const BriefStatCard: FC<BriefStatCardProps> = ({
  icon,
  value,
  label,
  sublabel,
  tone = 'muted',
  className,
}) => (
  <div className={cn('flex gap-2 p-1', className)}>
    <span
      className={cn(
        'inline-flex size-10 shrink-0 items-center justify-center rounded-lg [&_svg]:size-5',
        toneIcon[tone],
      )}
      aria-hidden
    >
      {icon}
    </span>
    <div className="min-w-0">
      <p className="text-foreground text-xs font-semibold">{label}</p>
      <p
        className={cn(
          'text-2xl leading-none font-bold tabular-nums',
          toneValue[tone],
        )}
      >
        {value}
      </p>
      {sublabel ? (
        <p className="text-muted truncate text-xs">{sublabel}</p>
      ) : null}
    </div>
  </div>
);
