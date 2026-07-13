import { DASHBOARD_COVERAGE_AREAS } from '@/data/dashboardCoverageAreas';
import { cn } from '@/lib/utils';
import type { FC } from 'react';

export type DashboardCoverageAreasProps = {
  className?: string;
};

/** Non-clickable coverage strip — communicates intelligence scope on the dashboard. */
export const DashboardCoverageAreas: FC<DashboardCoverageAreasProps> = ({
  className,
}) => (
  <section
    className={cn(
      'border-border bg-background-alt rounded-xl border p-4 sm:p-5 lg:p-6',
      className,
    )}
    aria-labelledby="dashboard-coverage-heading"
  >
    <h2
      id="dashboard-coverage-heading"
      className="font-heading text-foreground text-lg font-semibold tracking-tight sm:text-xl"
    >
      Coverage Areas
    </h2>
    <p className="text-muted mt-1 max-w-2xl text-sm leading-relaxed">
      The intelligence domains HiddenAlerts monitors for subscribers.
    </p>

    <ul className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-8 lg:gap-3">
      {DASHBOARD_COVERAGE_AREAS.map(area => {
        const Icon = area.icon;
        return (
          <li
            key={area.id}
            className="flex flex-col items-center gap-2 text-center"
          >
            <span className="border-border bg-surface text-muted-foreground inline-flex size-11 items-center justify-center rounded-full border">
              <Icon className="size-5" strokeWidth={1.5} aria-hidden />
            </span>
            <span className="text-muted text-[0.7rem] leading-snug font-medium sm:text-xs">
              {area.label}
            </span>
          </li>
        );
      })}
    </ul>
  </section>
);
