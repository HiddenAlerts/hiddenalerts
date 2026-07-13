import { cn } from '@/lib/utils';

import {
  SOURCES_WE_MONITOR,
  type MonitorSource,
} from '@/data/landingSources';

import { LandingSection } from './LandingSection';
import { SourceIcon } from './LandingSourceIcon';

function SourceItem({ source }: { source: MonitorSource }) {
  const isBrand =
    source.id === 'krebs' || source.id === 'bleeping';

  return (
    <li className="flex min-w-0 items-start gap-3">
      <SourceIcon
        variant={source.icon}
        className="text-muted-foreground/85 mt-0.5"
      />
      <div className="min-w-0">
        <p
          className={cn(
            'text-muted-foreground font-semibold tracking-wide',
            isBrand
              ? 'font-heading text-sm normal-case tracking-tight'
              : 'text-xs uppercase sm:text-sm',
          )}
        >
          {source.acronym}
        </p>
        {source.fullName ? (
          <p className="text-muted-foreground/70 mt-1 text-[0.65rem] leading-snug sm:text-xs">
            {source.fullName}
          </p>
        ) : null}
      </div>
    </li>
  );
}

export function LandingSourcesWeMonitor() {
  return (
    <LandingSection className="border-border-subtle border-t py-8 md:py-10">
      <h2 className="text-muted-foreground text-center text-xs font-semibold tracking-[0.2em] uppercase sm:text-sm">
        {SOURCES_WE_MONITOR.title}
      </h2>

      <ul className="mt-8 grid grid-cols-1 gap-x-8 gap-y-7 sm:grid-cols-2 lg:grid-cols-3">
        {SOURCES_WE_MONITOR.sources.map(source => (
          <SourceItem key={source.id} source={source} />
        ))}
      </ul>

      <p className="text-muted-foreground/80 mx-auto mt-8 max-w-2xl text-center text-xs leading-relaxed sm:text-sm">
        {SOURCES_WE_MONITOR.footnote}
      </p>
    </LandingSection>
  );
}
