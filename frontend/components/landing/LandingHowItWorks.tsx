import { ArrowRight } from 'lucide-react';

import { HOW_IT_WORKS } from '@/data/landing';

import { LandingSection, SectionHeading } from './LandingSection';

export function LandingHowItWorks() {
  return (
    <LandingSection
      id="how-it-works"
      ariaLabelledby="how-it-works-heading"
      className="border-border-subtle border-t py-6 md:py-8"
    >
      <SectionHeading
        id="how-it-works-heading"
        title={HOW_IT_WORKS.title}
        subtitle={HOW_IT_WORKS.subtitle}
        className="gap-2"
      />

      <ol className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-4 lg:gap-5">
        {HOW_IT_WORKS.steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <li key={step.step} className="relative flex flex-col items-center text-center">
              {index < HOW_IT_WORKS.steps.length - 1 ? (
                <ArrowRight
                  className="text-muted-foreground/40 absolute top-7 -right-3 hidden size-5 lg:block"
                  aria-hidden
                />
              ) : null}

              <span className="border-primary-500/40 text-primary-400 inline-flex size-14 items-center justify-center rounded-full border-2">
                <Icon className="size-6" aria-hidden />
              </span>

              <h3 className="text-foreground mt-3 text-sm font-semibold sm:text-base">
                {step.step}. {step.title}
              </h3>
              <p className="text-muted mt-1.5 max-w-[220px] text-sm leading-relaxed">
                {step.description}
              </p>
            </li>
          );
        })}
      </ol>
    </LandingSection>
  );
}
