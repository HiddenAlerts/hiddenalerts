import { ArrowRight } from 'lucide-react';

import { HOW_IT_WORKS } from '@/data/landing';

import { LandingSection, SectionHeading } from './LandingSection';

/** Compact four-step flow — matches approved mockup proportions. */
export function LandingHowItWorks() {
  return (
    <LandingSection
      id="how-it-works"
      ariaLabelledby="how-it-works-heading"
      className="border-border-subtle border-t py-5 md:py-6"
    >
      <SectionHeading
        id="how-it-works-heading"
        title={HOW_IT_WORKS.title}
        subtitle={HOW_IT_WORKS.subtitle}
        className="gap-1.5"
      />

      <ol className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:gap-3">
        {HOW_IT_WORKS.steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <li
              key={step.step}
              className="relative flex flex-col items-center text-center"
            >
              {index < HOW_IT_WORKS.steps.length - 1 ? (
                <ArrowRight
                  className="text-info/50 absolute top-5 -right-2.5 hidden size-4 lg:block"
                  aria-hidden
                />
              ) : null}

              <span className="border-primary-500/45 text-primary-400 inline-flex size-11 items-center justify-center rounded-full border">
                <Icon className="size-5" strokeWidth={1.75} aria-hidden />
              </span>

              <h3 className="text-foreground mt-2.5 text-sm font-semibold">
                {step.step}. {step.title}
              </h3>
              <p className="text-muted mt-1 max-w-[200px] text-xs leading-snug sm:text-[0.8125rem] sm:leading-relaxed">
                {step.description}
              </p>
            </li>
          );
        })}
      </ol>
    </LandingSection>
  );
}
