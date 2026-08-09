import { cn } from '@/lib/utils';
import type { LiveAlert } from '@/data/landing';

export type LandingLiveAlertRowProps = {
  alert: LiveAlert;
  className?: string;
};

/** Solid risk pills — same tokens as BriefRiskTag / app alerts. */
const levelBadge: Record<LiveAlert['level'], string> = {
  CRITICAL: 'bg-danger text-white',
  HIGH: 'bg-warning text-secondary-900',
  MEDIUM: 'bg-warning/80 text-secondary-900',
  LOW: 'bg-success text-secondary-900',
};

/** Non-interactive teaser row — risk_band badge + title + date • category. */
export function LandingLiveAlertRow({
  alert,
  className,
}: LandingLiveAlertRowProps) {
  const meta = [alert.timestamp, alert.category].filter(Boolean).join(' • ');

  return (
    <article
      className={cn(
        'border-border/50 flex flex-col gap-2 border-b py-3.5 last:border-b-0',
        className,
      )}
    >
      <span
        className={cn(
          'inline-flex w-fit items-center rounded-sm px-2 py-0.5 text-[0.65rem] font-bold tracking-wide uppercase',
          levelBadge[alert.level],
        )}
      >
        {alert.level === 'CRITICAL' || alert.level === 'HIGH'
          ? `${alert.level === 'CRITICAL' ? 'Critical' : 'High'} Risk`
          : alert.level}
      </span>

      <div className="min-w-0">
        <h3 className="text-foreground text-sm leading-snug font-semibold">
          {alert.title}
        </h3>
        {meta ? (
          <p className="text-muted-foreground mt-1.5 text-xs leading-relaxed">
            {meta}
          </p>
        ) : null}
      </div>
    </article>
  );
}
