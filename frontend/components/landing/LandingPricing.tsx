'use client';

import { buttonVariants } from '@/components/ui/button';
import { FREE_PLAN, PROFESSIONAL_PLAN } from '@/data/landing';
import { cn } from '@/lib/utils';
import { Check, Lock } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { LandingMailerLiteForm } from './LandingMailerLiteForm';
import { LandingSection } from './LandingSection';

export function LandingPricing() {
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>(
    'monthly',
  );

  return (
    <LandingSection
      id="pricing"
      ariaLabelledby="pricing-heading"
      className="border-border-subtle border-t py-8 md:py-10"
    >
      <div className="relative grid gap-5 lg:grid-cols-[1fr_auto_1.15fr] lg:items-stretch lg:gap-0">
        <article className="border-info/50 bg-background-alt/60 flex flex-col rounded-2xl border-2 p-6 sm:p-7">
          <h2
            id="pricing-heading"
            className="text-info text-sm font-bold tracking-[0.12em] uppercase"
          >
            {FREE_PLAN.title}
          </h2>
          <p className="text-muted mt-3 text-sm">{FREE_PLAN.intro}</p>

          <ul className="mt-5 space-y-2.5">
            {FREE_PLAN.features.map(feature => (
              <li
                key={feature}
                className="text-body flex items-start gap-2.5 text-sm"
              >
                <Check className="text-info mt-0.5 size-4 shrink-0" aria-hidden />
                <span>{feature}</span>
              </li>
            ))}
          </ul>

          <div className="mt-6">
            <LandingMailerLiteForm
              id="newsletter-signup"
              ariaLabel="Join free intelligence updates"
            />
          </div>
          <p className="text-muted-foreground mt-3 text-xs">{FREE_PLAN.footnote}</p>
        </article>

        <div className="flex items-center justify-center lg:px-3">
          <span className="border-border bg-surface text-muted flex size-10 items-center justify-center rounded-full border text-xs font-bold">
            VS
          </span>
        </div>

        <article className="border-primary-500/60 bg-background-alt/60 flex flex-col rounded-2xl border-2 p-6 sm:p-7">
          <h2 className="text-primary-400 text-sm font-bold tracking-[0.12em] uppercase">
            {PROFESSIONAL_PLAN.title}
          </h2>
          <p className="text-muted mt-3 text-sm leading-relaxed">
            {PROFESSIONAL_PLAN.description}
          </p>

          <div className="mt-6 flex flex-col gap-5 lg:flex-row lg:gap-6">
            <ul className="grid flex-1 gap-2 sm:grid-cols-2">
              {PROFESSIONAL_PLAN.features.map(feature => (
                <li
                  key={feature}
                  className="text-body flex items-start gap-2 text-sm"
                >
                  <Check
                    className="text-primary-400 mt-0.5 size-4 shrink-0"
                    aria-hidden
                  />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>

            <div className="flex shrink-0 flex-col gap-2 lg:w-36">
              <button
                type="button"
                onClick={() => setBillingCycle('monthly')}
                className={cn(
                  'border-border rounded-lg border p-3 text-left transition-colors',
                  billingCycle === 'monthly'
                    ? 'border-primary-500/50 bg-primary-500/10'
                    : 'bg-surface/40 hover:bg-surface/60',
                )}
              >
                <p className="text-foreground text-lg font-bold">
                  {PROFESSIONAL_PLAN.monthly.amount}
                  <span className="text-muted text-sm font-normal">
                    {PROFESSIONAL_PLAN.monthly.cadence}
                  </span>
                </p>
                <p className="text-muted-foreground text-xs">
                  {PROFESSIONAL_PLAN.monthly.note}
                </p>
              </button>
              <button
                type="button"
                onClick={() => setBillingCycle('annual')}
                className={cn(
                  'border-border relative rounded-lg border p-3 text-left transition-colors',
                  billingCycle === 'annual'
                    ? 'border-primary-500/50 bg-primary-500/10'
                    : 'bg-surface/40 hover:bg-surface/60',
                )}
              >
                {PROFESSIONAL_PLAN.annual.badge ? (
                  <span className="bg-primary-500 text-foreground absolute -top-2 right-2 rounded px-1.5 py-0.5 text-[0.6rem] font-bold">
                    {PROFESSIONAL_PLAN.annual.badge}
                  </span>
                ) : null}
                <p className="text-foreground text-lg font-bold">
                  {PROFESSIONAL_PLAN.annual.amount}
                  <span className="text-muted text-sm font-normal">
                    {PROFESSIONAL_PLAN.annual.cadence}
                  </span>
                </p>
                <p className="text-muted-foreground text-xs">
                  {PROFESSIONAL_PLAN.annual.note}
                </p>
              </button>
            </div>
          </div>

          <Link
            href={PROFESSIONAL_PLAN.cta.href}
            className={cn(
              buttonVariants({ variant: 'default', size: 'md' }),
              'mt-6 h-12 w-full gap-2 text-sm font-semibold',
            )}
          >
            <Lock className="size-4" aria-hidden />
            {PROFESSIONAL_PLAN.cta.label}
          </Link>
          <p className="text-muted-foreground mt-2 text-center text-xs">
            {PROFESSIONAL_PLAN.footnote}
          </p>
        </article>
      </div>
    </LandingSection>
  );
}
