// import { WaitlistForm } from './WaitlistForm';

import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const NEWSLETTER_URL = 'https://hiddenalerts.beehiiv.com';

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
          Detect fraud signals before they become headlines
        </h1>
        <p className="text-muted mx-auto mt-4 max-w-lg text-base sm:text-lg">
          AI-filtered signals from DOJ, SEC, FBI and more — ranked by risk so
          users can act early.
        </p>
        <div
          id="waitlist"
          className="mx-auto mt-8 flex w-full max-w-md flex-col items-center scroll-mt-24"
        >
          <a
            href={NEWSLETTER_URL}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              buttonVariants({ variant: 'default', size: 'md' }),
              'inline-flex h-11 min-w-[200px] items-center justify-center py-0 sm:min-w-[220px]',
            )}
          >
            Subscribe to newsletter
          </a>
          {/* <WaitlistForm /> */}
        </div>
      </div>
    </section>
  );
}
