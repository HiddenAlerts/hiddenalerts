import { VALUE_PROPS } from '@/data/landing';

import { LandingSection } from './LandingSection';

export function LandingValueProps() {
  return (
    <LandingSection
      className="border-border-subtle border-t py-8 md:py-10"
      ariaLabelledby="value-props-heading"
    >
      <h2 id="value-props-heading" className="sr-only">
        Why HiddenAlerts
      </h2>
      <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4 lg:gap-5">
        {VALUE_PROPS.map(item => {
          const Icon = item.icon;
          return (
            <li key={item.title} className="flex flex-col items-start gap-3">
              <span className="border-primary-500/45 text-primary-400 inline-flex size-11 items-center justify-center rounded-full border">
                <Icon className="size-5" strokeWidth={1.5} aria-hidden />
              </span>
              <div>
                <p className="text-foreground text-sm font-semibold leading-snug">
                  {item.title}
                </p>
                <p className="text-muted-foreground mt-1.5 text-xs leading-relaxed sm:text-sm">
                  {item.description}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    </LandingSection>
  );
}
