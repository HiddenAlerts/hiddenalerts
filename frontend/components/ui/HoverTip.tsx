import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

export type HoverTipProps = {
  /** Full text shown immediately on hover (replaces delayed native `title`). */
  label: string;
  children: ReactNode;
  className?: string;
  bubbleClassName?: string;
};

/**
 * Zero-delay tooltip for dense UI (native `title` waits ~800ms–1s in most browsers).
 */
export const HoverTip: FC<HoverTipProps> = ({
  label,
  children,
  className,
  bubbleClassName,
}) => {
  if (!label.trim()) return <>{children}</>;

  return (
    <span
      className={cn(
        'group/instant-tip relative isolate inline-flex max-w-full cursor-inherit',
        className,
      )}
    >
      {children}
      <span
        role="tooltip"
        className={cn(
          'border-border bg-surface-muted/98 text-foreground pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 w-max max-w-[min(26rem,calc(100vw-2rem))] -translate-x-1/2 rounded-md border px-2.5 py-1.5 text-left text-[0.7rem] leading-snug font-normal shadow-xl',
          'opacity-0 transition-none motion-reduce:transition-none',
          'group-hover/instant-tip:opacity-100',
          bubbleClassName,
        )}
      >
        {label}
      </span>
    </span>
  );
};
