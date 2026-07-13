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
        className="font-heading text-foreground text-center text-xl font-semibold tracking-[0.12em] uppercase sm:text-2xl"
      >
        Frequently Asked Questions
      </h2>

      <div className="mt-7 grid gap-4 sm:grid-cols-2">
        {LANDING_FAQ.map(item => (
          <details
            key={item.question}
            className="border-border bg-background-alt/60 group rounded-xl border"
          >
            <summary className="text-foreground hover:text-body flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-left text-sm font-medium sm:text-base [&::-webkit-details-marker]:hidden">
              <span className="min-w-0 pr-2">{item.question}</span>
              <ChevronDown
                className="text-muted size-5 shrink-0 transition-transform group-open:rotate-180"
                aria-hidden
              />
            </summary>
            <p className="text-muted px-5 pb-4 text-sm leading-relaxed">
              {item.answer}
            </p>
          </details>
        ))}
      </div>
    </LandingSection>
  );
}
