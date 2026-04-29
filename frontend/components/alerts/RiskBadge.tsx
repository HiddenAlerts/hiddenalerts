import { cn } from '@/lib/utils';

export type RiskBadgeProps = {
  label: string;
  className?: string;
};

export function RiskBadge({ label, className }: RiskBadgeProps) {
  const base =
    'inline-flex shrink-0 items-center rounded px-3 py-1 text-xs font-extrabold uppercase tracking-[0.08em]';

  if (label === 'HIGH') {
    return (
      <span className={cn(base, 'bg-danger/15 text-danger', className)}>
        {label}
      </span>
    );
  }

  if (label === 'MEDIUM') {
    return (
      <span className={cn(base, 'bg-warning/15 text-warning', className)}>
        {label}
      </span>
    );
  }

  if (label === 'LOW') {
    return (
      <span className={cn(base, 'bg-success/15 text-success', className)}>
        {label}
      </span>
    );
  }

  return (
    <span
      className={cn(
        base,
        'border-border bg-surface-muted/45 text-muted',
        className,
      )}
    >
      {label}
    </span>
  );
}
