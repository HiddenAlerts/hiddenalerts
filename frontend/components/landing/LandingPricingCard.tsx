import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Check } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

import type { BillingCycle, PricingPlan } from '@/data/landing';

import { LandingIconBadge } from './LandingIconBadge';

export type LandingPricingCardProps = {
  plan: PricingPlan;
  billingCycle: BillingCycle;
};

export const LandingPricingCard: FC<LandingPricingCardProps> = ({
  plan,
  billingCycle,
}) => {
  const price = plan.prices[billingCycle];
  const cta = plan.cta[billingCycle];
  const Icon = plan.icon;

  return (
    <article
      className={cn(
        'border-border bg-background-alt relative flex flex-col rounded-xl border p-6 sm:p-7',
        plan.highlighted && 'border-primary-500 shadow-[0_0_0_1px_rgb(238_68_66_/_0.35)]',
      )}
    >
      {plan.badge ? (
        <span className="bg-primary-500 text-foreground absolute -top-3 left-1/2 -translate-x-1/2 rounded-full px-3 py-0.5 text-[0.65rem] font-bold tracking-wide uppercase">
          {plan.badge}
        </span>
      ) : null}

      <LandingIconBadge icon={Icon} size="sm" />

      <h3 className="text-foreground mt-4 text-lg font-semibold">{plan.name}</h3>
      <p className="text-muted mt-1 text-sm leading-relaxed">{plan.description}</p>

      <div className="mt-5">
        <div className="flex items-baseline gap-1.5">
          <span className="text-foreground text-3xl font-bold tracking-tight sm:text-4xl">
            {price.amount}
          </span>
          {price.cadence ? (
            <span className="text-muted text-sm">{price.cadence}</span>
          ) : null}
        </div>
        {price.note ? (
          <p className="text-muted-foreground mt-1 text-xs">{price.note}</p>
        ) : null}
      </div>

      <Link
        href={cta.href}
        className={cn(
          buttonVariants({
            variant: plan.highlighted ? 'default' : 'outline',
            size: 'md',
          }),
          plan.highlighted
            ? ''
            : 'border-primary-500/50 text-primary-400 hover:bg-primary-500/10 hover:border-primary-500 bg-transparent',
          'mt-6 w-full text-sm font-semibold',
        )}
      >
        {cta.label}
      </Link>

      <ul className="mt-6 space-y-2.5">
        {plan.features.map(feature => (
          <li
            key={feature}
            className="text-body flex items-start gap-2 text-sm leading-relaxed"
          >
            <Check
              className="text-primary-400 mt-0.5 size-4 shrink-0"
              aria-hidden
            />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
    </article>
  );
};
