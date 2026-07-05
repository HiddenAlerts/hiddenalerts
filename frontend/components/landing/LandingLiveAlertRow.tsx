import { StatusTag } from '@/components/ui/StatusTag';
import { cn } from '@/lib/utils';
import type { LiveAlert } from '@/data/landing';

export type LandingLiveAlertRowProps = {
  alert: LiveAlert;
  className?: string;
};

const levelTone: Record<LiveAlert['level'], string> = {
  CRITICAL: 'text-danger',
  HIGH: 'text-danger',
  MEDIUM: 'text-warning',
};

/**
 * Single row in the "Live High-Risk Alerts" panel on the landing page.
 * Mirrors the dashboard alert card layout with rank, score, and category.
 */
export function LandingLiveAlertRow({
  alert,
  className,
}: LandingLiveAlertRowProps) {
  const Icon = alert.icon;

  return (
    <article
      className={cn(
        'border-border/70 flex gap-3 border-b py-4 last:border-b-0 sm:gap-4',
        className,
      )}
    >
      <div className="flex shrink-0 flex-col items-center gap-1.5">
        <span className="bg-primary-500 text-foreground flex size-7 items-center justify-center rounded-md text-xs font-bold tabular-nums">
          {alert.rank}
        </span>
        <span className="text-primary-400 text-xs font-semibold tabular-nums">
          {alert.score}/100
        </span>
        <span
          className={cn(
            'text-[0.65rem] font-bold tracking-wide uppercase',
            levelTone[alert.level],
          )}
        >
          {alert.level}
        </span>
      </div>

      <div className="min-w-0 flex-1">
        <h3 className="text-foreground text-sm leading-snug font-semibold sm:text-base">
          {alert.title}
        </h3>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusTag tone={alert.categoryTone} className="text-[0.7rem]">
            {alert.category}
          </StatusTag>
          <span className="text-muted-foreground text-xs">{alert.timestamp}</span>
        </div>
      </div>

      <span
        className="text-primary-400 bg-primary-500/10 border-primary-500/20 hidden size-10 shrink-0 items-center justify-center rounded-lg border sm:flex"
        aria-hidden
      >
        <Icon className="size-5" strokeWidth={1.75} />
      </span>
    </article>
  );
}
