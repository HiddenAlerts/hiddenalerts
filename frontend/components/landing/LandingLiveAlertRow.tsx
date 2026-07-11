import { StatusTag } from '@/components/ui/StatusTag';
import { cn } from '@/lib/utils';
import { ChevronRight } from 'lucide-react';
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

function ScoreCircle({ score, level }: { score: number; level: LiveAlert['level'] }) {
  const circumference = 2 * Math.PI * 18;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex shrink-0 flex-col items-center gap-1">
      <div className="relative size-12">
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
        <span className="text-foreground absolute inset-0 flex items-center justify-center text-[0.65rem] font-bold tabular-nums">
          {score}
        </span>
      </div>
      <span
        className={cn(
          'text-[0.6rem] font-bold tracking-wide uppercase',
          levelTone[level],
        )}
      >
        {level}
      </span>
    </div>
  );
}

export function LandingLiveAlertRow({
  alert,
  className,
}: LandingLiveAlertRowProps) {
  return (
    <article
      className={cn(
        'group border-border/60 hover:bg-surface/30 flex items-center gap-3 border-b py-4 transition-colors last:border-b-0 sm:gap-4',
        className,
      )}
    >
      <ScoreCircle score={alert.score} level={alert.level} />

      <div className="min-w-0 flex-1">
        <h3 className="text-foreground text-sm leading-snug font-semibold sm:text-[0.9rem]">
          {alert.title}
        </h3>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusTag tone={alert.categoryTone} className="text-[0.65rem]">
            {alert.category}
          </StatusTag>
          <span className="text-muted-foreground text-xs">{alert.timestamp}</span>
        </div>
      </div>

      <ChevronRight
        className="text-primary-500 size-5 shrink-0 opacity-60 transition-opacity group-hover:opacity-100"
        aria-hidden
      />
    </article>
  );
}
