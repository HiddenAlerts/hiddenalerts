'use client';

import { cn } from '@/lib/utils';
import { AlertTriangle } from 'lucide-react';
import { useState } from 'react';

import type { BillingCycle } from '@/data/landing';
import { PRICING_SECTION } from '@/data/landing';

import { LandingPricingCard } from './LandingPricingCard';
import { LandingSection } from './LandingSection';

export function LandingPricing() {
  const [billingCycle, setBillingCycle] = useState<BillingCycle>('monthly');
  const section = PRICING_SECTION;

  return (
    <LandingSection
      id="pricing"
      ariaLabelledby="pricing-heading"
      className="border-border-subtle border-t"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2
            id="pricing-heading"
            className="font-heading text-foreground text-2xl font-semibold tracking-tight text-balance sm:text-3xl"
          >
            {section.title}
          </h2>
          <p className="text-primary-400 mt-2 text-sm font-semibold">
            {section.introNote}
          </p>
        </div>

        <div className="flex flex-col items-start gap-3 sm:items-end">
          <p className="text-muted flex items-center gap-2 text-xs sm:text-sm">
            <AlertTriangle className="text-warning size-4 shrink-0" aria-hidden />
            {section.urgencyNote}
          </p>

          <div
            className="border-border bg-surface/50 inline-flex rounded-lg border p-1"
            role="group"
            aria-label="Billing cycle"
          >
            {(['monthly', 'annual'] as const).map(cycle => (
              <button
                key={cycle}
                type="button"
                onClick={() => setBillingCycle(cycle)}
                className={cn(
                  'rounded-md px-3 py-1.5 text-xs font-semibold transition-colors sm:px-4 sm:text-sm',
                  billingCycle === cycle
                    ? 'bg-primary-500 text-white'
                    : 'text-muted hover:text-foreground',
                )}
              >
                {section.toggle[cycle]}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-10 grid gap-6 lg:grid-cols-3">
        {section.plans.map(plan => (
          <LandingPricingCard
            key={plan.id}
            plan={plan}
            billingCycle={billingCycle}
          />
        ))}
      </div>
    </LandingSection>
  );
}
