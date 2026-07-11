import { cn } from '@/lib/utils';

import { SOURCES_WE_MONITOR } from '@/data/landingSources';

import { LandingSection } from './LandingSection';
import { SourceIcon } from './LandingSourceIcon';

function SourceItem({
  acronym,
  fullName,
  variant,
}: {
  acronym: string;
  fullName?: string;
  variant: (typeof SOURCES_WE_MONITOR.sources)[number]['variant'];
}) {
  const hasIcon = variant === 'seal' || variant === 'shield';
  const isBrand = variant === 'brand';

  return (
    <li className="flex min-w-0 flex-col items-center text-center lg:items-start lg:text-left">
      <div
        className={cn(
          'flex items-center gap-2.5',
          !hasIcon && 'flex-col items-center lg:items-start',
        )}
      >
        {hasIcon ? (
          <SourceIcon
            variant={variant}
            className="text-muted-foreground/80"
          />
        ) : null}

        <div className="min-w-0">
          <p
            className={cn(
              'text-muted-foreground font-semibold tracking-wide uppercase',
              isBrand
                ? 'text-xs normal-case tracking-normal sm:text-sm'
                : 'text-xs sm:text-sm',
              acronym === 'KrebsOnSecurity' && 'font-heading tracking-tight',
              acronym === 'BleepingComputer' && 'font-heading tracking-tight',
            )}
          >
            {acronym}
          </p>
          {fullName ? (
            <p className="text-muted-foreground/70 mt-0.5 max-w-[130px] text-[0.6rem] leading-tight sm:max-w-[150px] sm:text-[0.65rem]">
              {fullName}
            </p>
          ) : null}
        </div>
      </div>
    </li>
  );
}

export function LandingSourcesWeMonitor() {
  return (
    <LandingSection className="border-border-subtle border-t py-14 md:py-20">
      <h2 className="text-muted-foreground text-center text-xs font-semibold tracking-[0.2em] uppercase sm:text-sm">
        {SOURCES_WE_MONITOR.title}
      </h2>

      <ul className="mt-10 grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 md:grid-cols-5 lg:flex lg:flex-wrap lg:items-start lg:justify-center lg:gap-x-6 lg:gap-y-6 xl:gap-x-10">
        {SOURCES_WE_MONITOR.sources.map(source => (
          <SourceItem
            key={source.id}
            acronym={source.acronym}
            fullName={source.fullName}
            variant={source.variant}
          />
        ))}
      </ul>

      <p className="text-muted-foreground/80 mx-auto mt-10 max-w-2xl text-center text-xs leading-relaxed sm:text-sm">
        {SOURCES_WE_MONITOR.footnote}
      </p>
    </LandingSection>
  );
}
