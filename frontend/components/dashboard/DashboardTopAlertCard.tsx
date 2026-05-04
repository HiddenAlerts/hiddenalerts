import type {
  DashboardTopAlertIconVariant,
  DashboardTopAlertItem,
  DashboardTopAlertRiskTone,
  DashboardTopAlertTagSegment,
} from '@/data/dashboardTopAlerts';
import { formatTopAlertFooterTimestampUtc } from '@/lib/formatDashboardDate';
import { cn } from '@/lib/utils';
import { Calendar, Landmark, Lock, UserRound, Wallet } from 'lucide-react';
import type { FC } from 'react';

const scoreToneStyles: Record<DashboardTopAlertRiskTone, { pill: string }> = {
  high: {
    pill: 'border-danger text-danger',
  },
  medium: {
    pill: 'border-warning text-warning',
  },
  low: {
    pill: 'border-success text-success',
  },
};

function iconBlock(
  variant: DashboardTopAlertIconVariant,
  riskTone: DashboardTopAlertRiskTone,
) {
  const highWrap = 'bg-danger text-white';
  const walletWrap = 'bg-surface-muted text-warning ring-1 ring-border/80';

  if (variant === 'landmark') {
    return (
      <div
        className={cn(
          'flex size-10 shrink-0 items-center justify-center rounded-full sm:size-11',
          riskTone === 'high' ? highWrap : 'bg-surface-muted text-body',
        )}
      >
        <Landmark
          className="size-[18px] sm:size-5"
          strokeWidth={1.75}
          aria-hidden
        />
      </div>
    );
  }
  if (variant === 'wallet') {
    return (
      <div
        className={cn(
          'flex size-10 shrink-0 items-center justify-center rounded-full sm:size-11',
          walletWrap,
        )}
      >
        <Wallet
          className="size-[18px] sm:size-5"
          strokeWidth={1.75}
          aria-hidden
        />
      </div>
    );
  }
  return (
    <div
      className={cn(
        'relative flex size-10 shrink-0 items-center justify-center rounded-full sm:size-11',
        riskTone === 'high' ? highWrap : 'bg-surface-muted text-body',
      )}
    >
      <UserRound
        className="size-[18px] sm:size-5"
        strokeWidth={1.75}
        aria-hidden
      />
      <span className="bg-background/25 absolute -right-0.5 -bottom-0.5 flex size-4 items-center justify-center rounded-full">
        <Lock className="size-2.5" strokeWidth={2.5} aria-hidden />
      </span>
    </div>
  );
}

function TagSegments({ tags }: { tags: DashboardTopAlertTagSegment[] }) {
  return (
    <p className="text-muted mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs leading-snug">
      {tags.map((tag, i) => (
        <span
          key={`${tag.text}-${i}`}
          className="inline-flex items-center gap-1"
        >
          {i > 0 ? (
            <span className="text-muted-foreground/55" aria-hidden>
              •
            </span>
          ) : null}
          {tag.dot ? (
            <span
              className="bg-danger size-1.5 shrink-0 rounded-full"
              aria-hidden
            />
          ) : null}
          <span
            className={cn(
              tag.tone === 'info' && 'text-info',
              (!tag.tone || tag.tone === 'default') && 'text-body',
            )}
          >
            {tag.text}
          </span>
        </span>
      ))}
    </p>
  );
}

export type DashboardTopAlertCardProps = {
  alert: DashboardTopAlertItem;
  riskTone?: DashboardTopAlertRiskTone;
  className?: string;
};

export const DashboardTopAlertCard: FC<DashboardTopAlertCardProps> = ({
  alert,
  riskTone = 'high',
  className,
}) => {
  const scoreStyle = scoreToneStyles[riskTone];
  const footer = formatTopAlertFooterTimestampUtc(alert.occurredAt);

  return (
    <article
      className={cn(
        'border-border bg-background-alt/80 flex flex-col rounded-lg border p-3.5 shadow-xs sm:p-4',
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="bg-danger flex size-6 shrink-0 items-center justify-center rounded text-xs font-bold text-white tabular-nums">
          {alert.rank}
        </span>
        <span
          className={cn(
            'shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-semibold tabular-nums',
            scoreStyle.pill,
          )}
        >
          {alert.score}/100
        </span>
      </div>

      <div className="mt-3 flex gap-3">
        {iconBlock(alert.iconVariant, riskTone)}
        <div className="min-w-0 flex-1">
          <h3 className="font-heading text-foreground line-clamp-2 text-sm leading-snug font-semibold tracking-tight sm:text-[0.95rem]">
            {alert.title}
          </h3>
          <TagSegments tags={alert.tags} />
        </div>
      </div>

      <p className="text-muted mt-2 line-clamp-3 text-xs leading-relaxed">
        {alert.description}
      </p>

      <p className="text-muted mt-3 flex items-center gap-1.5 text-[0.7rem] leading-snug">
        <Calendar
          className="text-muted-foreground size-3.5 shrink-0"
          strokeWidth={1.5}
          aria-hidden
        />
        <span>{footer}</span>
      </p>
    </article>
  );
};
