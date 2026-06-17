import { buttonVariants } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { Check, Mail } from 'lucide-react';

import { NEWSLETTER_CTA } from '@/data/landing';

import { LandingSection } from './LandingSection';

export function LandingNewsletterCta() {
  const cta = NEWSLETTER_CTA;

  return (
    <LandingSection className="py-10 md:py-14">
      <div className="border-primary-500/30 bg-[linear-gradient(135deg,rgba(112,29,28,0.18),rgba(13,21,37,0.55))] rounded-2xl border p-6 sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex gap-4">
            <span
              className="text-primary-400 bg-primary-500/10 border-primary-500/20 hidden size-12 shrink-0 items-center justify-center rounded-xl border sm:flex"
              aria-hidden
            >
              <Mail className="size-6" />
            </span>
            <div>
              <h2 className="font-heading text-foreground text-lg font-semibold tracking-tight sm:text-xl">
                {cta.title}
              </h2>
              <p className="text-muted mt-1 text-sm">{cta.description}</p>
            </div>
          </div>

          <form
            action={cta.actionUrl}
            method="get"
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-full max-w-md flex-col gap-2 sm:flex-row sm:items-center"
          >
            <Input
              name="email"
              type="email"
              inputSize="md"
              placeholder={cta.placeholder}
              autoComplete="email"
              required
              aria-label="Work email address"
              parentStyles="w-full min-w-0 sm:flex-1"
            />
            <button
              type="submit"
              className={cn(
                buttonVariants({ variant: 'default', size: 'md' }),
                'h-11 shrink-0 px-6 text-sm font-semibold sm:min-w-[150px]',
              )}
            >
              {cta.buttonLabel}
            </button>
          </form>
        </div>

        <ul className="mt-6 flex flex-wrap gap-x-6 gap-y-2">
          {cta.perks.map(perk => (
            <li
              key={perk}
              className="text-body flex items-center gap-2 text-xs sm:text-sm"
            >
              <Check className="text-primary-400 size-4 shrink-0" aria-hidden />
              <span>{perk}</span>
            </li>
          ))}
        </ul>
      </div>
    </LandingSection>
  );
}
