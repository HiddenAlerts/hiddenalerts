import { PROBLEM_SECTION } from '@/data/landing';

import { LandingSection } from './LandingSection';

export function LandingProblem() {
  return (
    <LandingSection
      ariaLabelledby="problem-heading"
      className="bg-[radial-gradient(circle_at_15%_20%,rgba(238,68,66,0.16),transparent_55%),linear-gradient(180deg,rgba(112,29,28,0.22),rgba(7,13,25,0.4))]"
      containerClassName="max-w-6xl"
    >
      <div className="border-primary-900/40 rounded-2xl border bg-[linear-gradient(180deg,rgba(112,29,28,0.18),rgba(13,21,37,0.4))] p-6 sm:p-9">
        <h2
          id="problem-heading"
          className="font-heading text-foreground text-2xl font-semibold tracking-tight sm:text-3xl"
        >
          {PROBLEM_SECTION.title}
        </h2>

        <div className="mt-8 grid gap-8 lg:grid-cols-[1.6fr_1fr] lg:gap-12">
          <ul className="grid gap-6 sm:grid-cols-3">
            {PROBLEM_SECTION.points.map(point => {
              const Icon = point.icon;
              return (
                <li key={point.title} className="flex flex-col gap-3">
                  <span className="text-primary-400 inline-flex" aria-hidden>
                    <Icon className="size-6" />
                  </span>
                  <h3 className="text-foreground text-sm font-semibold sm:text-base">
                    {point.title}
                  </h3>
                  <p className="text-body/80 text-xs leading-relaxed sm:text-sm">
                    {point.description}
                  </p>
                </li>
              );
            })}
          </ul>

          <div className="border-primary-500/30 bg-primary-500/10 flex flex-col justify-center gap-2 rounded-xl border p-5">
            <span className="text-primary-300 text-sm font-semibold">
              {PROBLEM_SECTION.resultLabel}
            </span>
            <p className="text-foreground text-base leading-relaxed font-medium sm:text-lg">
              {PROBLEM_SECTION.resultText}
            </p>
          </div>
        </div>
      </div>
    </LandingSection>
  );
}
