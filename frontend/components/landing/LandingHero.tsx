import { WaitlistForm } from './WaitlistForm';

export function LandingHero() {
  return (
    <section
      id="top"
      className="relative scroll-mt-16 overflow-hidden px-4 pt-10 pb-12 sm:px-6 sm:pt-14 sm:pb-16 lg:px-8"
    >
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-30"
        aria-hidden
      >
        <div className="bg-primary-500/25 absolute -top-40 left-1/2 h-[360px] w-[360px] -translate-x-1/2 rounded-full blur-3xl" />
      </div>

      <div className="mx-auto max-w-2xl text-center">
        <h1 className="font-heading text-foreground text-3xl leading-tight font-semibold tracking-tight sm:text-4xl lg:text-[2.75rem]">
          Signals before the headlines.
        </h1>
        <p className="text-muted mx-auto mt-4 max-w-lg text-base sm:text-lg">
          Early fraud, scam, and financial threat signals from curated
          sources—for analysts and fincrime teams validating risk early.
        </p>
        <div className="mt-8">
          <WaitlistForm />
        </div>
      </div>
    </section>
  );
}
