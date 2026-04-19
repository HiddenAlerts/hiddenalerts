import { LayoutGrid } from 'lucide-react';

import { cn } from '@/lib/utils';

type LandingLogoProps = {
  className?: string;
  iconClassName?: string;
  textClassName?: string;
};

export function LandingLogo({
  className,
  iconClassName,
  textClassName,
}: LandingLogoProps) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <span
        className={cn(
          'bg-primary-500/15 text-primary-500 inline-flex size-9 items-center justify-center rounded-md',
          iconClassName,
        )}
      >
        <LayoutGrid className="size-5 shrink-0" strokeWidth={2} aria-hidden />
      </span>
      <span
        className={cn(
          'font-heading text-foreground text-lg font-semibold tracking-tight',
          textClassName,
        )}
      >
        HiddenAlerts
      </span>
    </span>
  );
}
