import { ChevronDown } from 'lucide-react';

const items = [
  {
    question: 'What is HiddenAlerts?',
    answer:
      'A real-time fraud intelligence feed surfacing early signals from trusted sources.',
  },
  {
    question: 'What is included in the MVP?',
    answer:
      'Curated alerts, risk ranking, and a simple dashboard focused on early detection.',
  },
  {
    question: 'How does access work?',
    answer:
      'Join the waitlist and get early access as we roll out to initial users.',
  },
] as const;

export function LandingFAQ() {
  return (
    <section
      id="faq"
      className="border-border-subtle scroll-mt-20 border-t px-4 py-16 md:px-6"
      aria-labelledby="faq-heading"
    >
      <div className="mx-auto max-w-5xl">
        <h2 id="faq-heading" className="font-heading text-foreground text-center text-2xl font-semibold tracking-tight sm:text-3xl">
          FAQ
        </h2>

        <div className="mt-4 space-y-0">
          {items.map((item) => (
            <details
              key={item.question}
              className="border-border group border-b first:border-t"
            >
              <summary className="text-foreground hover:text-body flex cursor-pointer list-none items-center justify-between gap-3 py-3.5 text-left text-sm font-medium sm:text-base [&::-webkit-details-marker]:hidden">
                <span className="min-w-0 pr-2">{item.question}</span>
                <ChevronDown
                  className="text-muted size-5 shrink-0 group-open:rotate-180"
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
