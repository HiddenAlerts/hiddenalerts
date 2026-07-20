import { VALUE_PROPS } from '@/data/landing';

import { LandingSection } from './LandingSection';

export function LandingValueProps() {
  return (
    <LandingSection
      className="border-border-subtle border-t py-5 md:py-6"
      ariaLabelledby="value-props-heading"
    >
      <h2 id="value-props-heading" className="sr-only">
        Why HiddenAlerts
      </h2>
      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4 lg:gap-4">
        {VALUE_PROPS.map(item => {
          const Icon = item.icon;
          return (
            <li key={item.title} className="flex flex-col items-start gap-2.5">
              <span className="border-primary-500/45 text-primary-400 inline-flex size-10 items-center justify-center rounded-full border">
                <Icon className="size-4" strokeWidth={1.5} aria-hidden />
              </span>
              <div>
                <p className="text-foreground text-sm font-semibold leading-snug">
                  {item.title}
                </p>
                <p className="text-muted-foreground mt-1 text-xs leading-relaxed sm:text-sm">
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
