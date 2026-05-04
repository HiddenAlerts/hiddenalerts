import { cn } from '@/lib/utils';

export type RiskBadgeProps = {
  label: string;
  className?: string;
  /** `outline` matches alert list cards (border + text). Default `solid`. */
  variant?: 'solid' | 'outline';
};

export function RiskBadge({
  label,
  className,
  variant = 'solid',
}: RiskBadgeProps) {
  const base =
    'inline-flex shrink-0 items-center rounded-sm px-2.5 py-1 text-xs font-semibold';

  const solidBase =
    variant === 'solid'
      ? 'font-extrabold uppercase tracking-[0.08em]'
      : 'tracking-tight';

  if (label === 'HIGH') {
    return (
      <span
        className={cn(
          base,
          solidBase,
          variant === 'outline'
            ? 'bg-danger-500/10 border-danger text-danger border'
            : 'bg-danger/15 text-danger',
          className,
        )}
      >
        {variant === 'outline' ? 'High' : label}
      </span>
    );
  }

  if (label === 'MEDIUM') {
    return (
      <span
        className={cn(
          base,
          solidBase,
          variant === 'outline'
            ? 'border-warning bg-warning-500/10 text-warning border'
            : 'bg-warning/15 text-warning',
          className,
        )}
      >
        {variant === 'outline' ? 'Medium' : label}
      </span>
    );
  }

  if (label === 'LOW') {
    return (
      <span
        className={cn(
          base,
          solidBase,
          variant === 'outline'
            ? 'border-success bg-success-500/10 text-success border'
            : 'bg-success/15 text-success',
          className,
        )}
      >
        {variant === 'outline' ? 'Low' : label}
      </span>
    );
  }

  return (
    <span
      className={cn(
        base,
        solidBase,
        variant === 'outline'
          ? 'border-border text-muted border'
          : 'border-border bg-surface-muted/45 text-muted',
        className,
      )}
    >
      {label}
    </span>
  );
}
