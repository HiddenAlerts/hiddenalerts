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
    <li className="flex min-w-0 items-start gap-2">
      <SourceIcon
        variant={source.icon}
        className="text-muted-foreground/85 mt-0.5 size-8"
      />
      <div className="min-w-0">
        <p
          className={cn(
            'text-muted-foreground font-semibold tracking-wide',
            isBrand
              ? 'font-heading text-[0.65rem] normal-case tracking-tight'
              : 'text-[0.65rem] uppercase',
          )}
        >
          {source.acronym}
        </p>
        {source.fullName ? (
          <p className="text-muted-foreground/70 mt-0.5 text-[0.6rem] leading-snug">
            {source.fullName}
          </p>
        ) : null}
      </div>
    </li>
  );
}

export function LandingSourcesWeMonitor() {
  return (
    <LandingSection
      className="border-border-subtle border-t py-5 md:py-6"
      containerClassName="max-w-7xl"
    >
      <h2 className="text-muted-foreground text-center text-xs font-semibold tracking-[0.2em] uppercase sm:text-sm">
        {SOURCES_WE_MONITOR.title}
      </h2>

      <ul className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-9 lg:gap-x-3">
        {SOURCES_WE_MONITOR.sources.map(source => (
          <SourceItem key={source.id} source={source} />
        ))}
      </ul>

      <p className="text-muted-foreground/80 mx-auto mt-5 max-w-2xl text-center text-xs leading-relaxed">
        {SOURCES_WE_MONITOR.footnote}
      </p>
    </LandingSection>
  );
}
