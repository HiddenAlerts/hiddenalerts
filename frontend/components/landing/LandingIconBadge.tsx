import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

export type LandingIconBadgeProps = {
  icon: LucideIcon;
  /** Visual size of the badge container. */
  size?: 'sm' | 'md' | 'lg';
  className?: string;
};

const containerSize = {
  sm: 'size-9 rounded-lg',
  md: 'size-11 rounded-xl',
  lg: 'size-14 rounded-2xl',
} as const;

const iconSize = {
  sm: 'size-4',
  md: 'size-5',
  lg: 'size-6',
} as const;

/** Rounded, tinted container for a Lucide icon — used across landing sections. */
export function LandingIconBadge({
  icon: Icon,
  size = 'md',
  className,
}: LandingIconBadgeProps) {
  return (
    <span
      className={cn(
        'bg-primary-500/12 text-primary-400 border-primary-500/20 inline-flex shrink-0 items-center justify-center border',
        containerSize[size],
        className,
      )}
    >
      <Icon className={iconSize[size]} aria-hidden />
    </span>
  );
}
