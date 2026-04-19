import { cn } from '@/lib/utils';
import type { AlertBadgeTone } from '@/types/alert';
import type { FC } from 'react';

const toneClass: Record<AlertBadgeTone, string> = {
  danger: 'bg-danger-muted text-danger',
  success: 'bg-success-muted text-success',
  info: 'bg-info-muted text-info',
  warning: 'bg-warning-muted text-warning',
};

export type BadgeProps = {
  children: string;
  tone?: AlertBadgeTone;
  className?: string;
};

export const Badge: FC<BadgeProps> = ({
  children,
  tone = 'info',
  className,
}) => (
  <span
    className={cn(
      'inline-flex min-w-[5.5rem] items-center justify-center rounded-md px-3 py-1 text-xs font-medium',
      toneClass[tone],
      className,
    )}
  >
    {children}
  </span>
);
