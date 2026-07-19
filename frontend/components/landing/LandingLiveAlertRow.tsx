import { cn } from '@/lib/utils';
import type { LiveAlert } from '@/data/landing';

export type LandingLiveAlertRowProps = {
  alert: LiveAlert;
  className?: string;
};

const levelTone: Record<LiveAlert['level'], string> = {
  CRITICAL: 'text-primary-500',
  HIGH: 'text-primary-500',
  MEDIUM: 'text-warning',
};

function ScoreCircle({ score, level }: { score: number; level: LiveAlert['level'] }) {
  const circumference = 2 * Math.PI * 18;
  const offset = circumference - (Math.min(score, 100) / 100) * circumference;

  return (
    <div className="flex shrink-0 flex-col items-center gap-0.5">
      <div className="relative size-11 sm:size-12">
        <svg viewBox="0 0 44 44" className="size-full -rotate-90" aria-hidden>
          <circle
            cx="22"
            cy="22"
            r="18"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            className="text-border"
          />
          <circle
            cx="22"
            cy="22"
            r="18"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="text-primary-500"
          />
        </svg>
        <span className="text-foreground absolute inset-0 flex items-center justify-center text-[0.7rem] font-bold tabular-nums">
          {score}
        </span>
      </div>
      <span
        className={cn(
          'text-[0.55rem] font-bold tracking-wide uppercase',
          levelTone[level],
        )}
      >
        {level}
      </span>
    </div>
  );
}

/** Non-interactive preview row — score ring + title + date • category. */
export function LandingLiveAlertRow({
  alert,
  className,
}: LandingLiveAlertRowProps) {
  const meta = [alert.timestamp, alert.category].filter(Boolean).join(' • ');

  return (
    <article
      className={cn(
        'border-border/50 flex items-start gap-3 border-b py-3.5 last:border-b-0 sm:gap-3.5',
        className,
      )}
    >
      <ScoreCircle score={alert.score} level={alert.level} />

      <div className="min-w-0 flex-1 pt-0.5">
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
