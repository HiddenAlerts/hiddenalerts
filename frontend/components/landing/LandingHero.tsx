import { WaitlistForm } from './WaitlistForm';

export function LandingHero() {
  return (
    <section
      id="top"
      className="relative flex scroll-mt-16 items-center overflow-hidden px-4 py-20 md:px-6 md:py-20"
    >
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-30"
        aria-hidden
      >
        <div className="bg-primary-500/25 absolute -top-40 left-1/2 h-[360px] w-[360px] -translate-x-1/2 rounded-full blur-3xl" />
      </div>

      <div className="mx-auto max-w-5xl text-center">
        <h1 className="font-heading text-foreground text-balance text-4xl leading-tight font-bold tracking-tight sm:text-5xl lg:text-[3.6rem]">
          Detect fraud signals before they become headlines
        </h1>
        <p className="text-muted mx-auto mt-4 max-w-2xl text-lg sm:text-xl">
          AI-filtered alerts from DOJ, SEC, FBI and more — ranked by risk so you
          can act early.
        </p>
        <div
          className="mx-auto mt-6 w-full max-w-md scroll-mt-24"
        >
          <WaitlistForm microText="Early access to high-risk fraud alerts. Limited rollout." />
        </div>
      </div>
    </section>
  );
}
