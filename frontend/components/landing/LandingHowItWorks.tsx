import { ArrowRight } from 'lucide-react';

import { HOW_IT_WORKS } from '@/data/landing';

import { LandingIconBadge } from './LandingIconBadge';
import { LandingSection, SectionHeading } from './LandingSection';

export function LandingHowItWorks() {
  return (
    <LandingSection
      id="how-it-works"
      ariaLabelledby="how-it-works-heading"
      className="border-border-subtle border-t"
    >
      <SectionHeading
        id="how-it-works-heading"
        title={HOW_IT_WORKS.title}
        subtitle={HOW_IT_WORKS.subtitle}
      />

      <ol className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-6">
        {HOW_IT_WORKS.steps.map((step, index) => (
          <li key={step.step} className="relative flex flex-col">
            {index < HOW_IT_WORKS.steps.length - 1 ? (
              <ArrowRight
                className="text-muted-foreground/50 absolute top-5 -right-3 hidden size-5 lg:block"
                aria-hidden
              />
            ) : null}

            <LandingIconBadge icon={step.icon} size="md" />
            <h3 className="text-foreground mt-4 text-sm font-semibold sm:text-base">
              {step.step}. {step.title}
            </h3>
            <p className="text-muted mt-2 text-sm leading-relaxed">
              {step.description}
            </p>
          </li>
        ))}
      </ol>
    </LandingSection>
  );
}
