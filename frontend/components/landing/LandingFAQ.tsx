import { ChevronDown } from 'lucide-react';

const items = [
  {
    question: 'What is HiddenAlerts?',
    answer:
      'A subscription-style fraud intelligence dashboard: curated sources, structured alerts, and basic filters so you can explore early signals.',
  },
  {
    question: 'What is in the MVP?',
    answer:
      'Aggregation from trusted sources, stored alerts, clear presentation, and simple filtering—not full automation or advanced analytics yet.',
  },
  {
    question: 'How does the waitlist work?',
    answer:
      'Leave your email and we will invite early analysts and fincrime users as cohorts open. No account required today.',
  },
] as const;

export function LandingFAQ() {
  return (
    <section
      id="faq"
      className="border-border-subtle scroll-mt-20 border-t px-4 py-12 sm:px-6 sm:py-14 lg:px-8"
      aria-labelledby="faq-heading"
    >
      <div className="mx-auto max-w-xl">
        <h2
          id="faq-heading"
          className="font-heading text-foreground text-center text-2xl font-semibold tracking-tight sm:text-3xl"
        >
          Common questions
        </h2>

        <div className="mt-8 space-y-0">
          {items.map((item) => (
            <details
              key={item.question}
              className="border-border group border-b first:border-t"
            >
              <summary className="text-foreground hover:text-body flex cursor-pointer list-none items-center justify-between gap-3 py-3.5 text-left text-sm font-medium transition-colors sm:text-base [&::-webkit-details-marker]:hidden">
                <span className="min-w-0 pr-2">{item.question}</span>
                <ChevronDown
                  className="text-muted size-5 shrink-0 transition-transform duration-200 group-open:rotate-180"
                  aria-hidden
                />
              </summary>
              <p className="text-muted pb-3.5 text-sm leading-relaxed">
                {item.answer}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
