import { ChevronDown } from 'lucide-react';

import { LANDING_FAQ } from '@/data/landing';

import { LandingSection } from './LandingSection';

export function LandingFAQ() {
  return (
    <LandingSection
      id="faq"
      ariaLabelledby="faq-heading"
      className="border-border-subtle border-t"
    >
      <h2
        id="faq-heading"
        className="font-heading text-foreground text-center text-2xl font-semibold tracking-tight sm:text-3xl"
      >
        FAQ
      </h2>

      <div className="mx-auto mt-8 max-w-3xl space-y-0">
        {LANDING_FAQ.map(item => (
          <details
            key={item.question}
            className="border-border group border-b first:border-t"
          >
            <summary className="text-foreground hover:text-body flex cursor-pointer list-none items-center justify-between gap-3 py-4 text-left text-sm font-medium sm:text-base [&::-webkit-details-marker]:hidden">
              <span className="min-w-0 pr-2">{item.question}</span>
              <ChevronDown
                className="text-muted size-5 shrink-0 transition-transform group-open:rotate-180"
                aria-hidden
              />
            </summary>
            <p className="text-muted pb-4 text-sm leading-relaxed">
              {item.answer}
            </p>
          </details>
        ))}
      </div>
    </LandingSection>
  );
}
