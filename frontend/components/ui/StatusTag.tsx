import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

export type StatusTone = 'success' | 'neutral' | 'warning' | 'danger' | 'info';

const toneClass: Record<StatusTone, string> = {
  success: 'bg-success-muted text-success',
  neutral: 'bg-surface-muted text-muted',
  warning: 'bg-warning-muted text-warning',
  danger: 'bg-danger-muted text-danger',
  info: 'bg-info-muted text-info',
};

export type StatusTagProps = {
  children: ReactNode;
  tone?: StatusTone;
  className?: string;
};

/**
 * Small status pill used in table rows (e.g. "Published", "Draft").
 */
export const StatusTag: FC<StatusTagProps> = ({
  children,
  tone = 'neutral',
  className,
}) => (
  <span
    className={cn(
      'inline-flex items-center justify-center rounded-md px-2.5 py-1 text-xs font-medium',
      toneClass[tone],
      className,
    )}
  >
    {children}
  </span>
);
