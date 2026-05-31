'use client';

import { LandingFooter } from '@/components/landing/LandingFooter';
import { LandingHeader } from '@/components/landing/LandingHeader';
import { Button } from '@/components/ui/button';
import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/contexts/AuthProvider';
import { createCheckout } from '@/lib/api/billing';
import type { HttpRequestError } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import type { BillingPlan } from '@/types/billing';
import { Check, LogOut } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

type Plan = {
  id: BillingPlan;
  name: string;
  priceLabel: string;
  cadence: string;
  description: string;
  badge?: string;
  features: string[];
  highlighted?: boolean;
};

const PLANS: Plan[] = [
  {
    id: 'monthly',
    name: 'Monthly',
    priceLabel: '$49',
    cadence: '/ month',
    description: 'Flexible access — cancel any time.',
    features: [
      'Real-time fraud and sanctions alerts',
      'Search across enriched intelligence',
      'Risk-scored daily digest',
      'Email + dashboard notifications',
    ],
  },
  {
    id: 'annual',
    name: 'Annual',
    priceLabel: '$490',
    cadence: '/ year',
    description: 'Two months free vs. monthly billing.',
    badge: 'Save ~17%',
    highlighted: true,
    features: [
      'Everything in Monthly',
      'Priority support',
      'Lock in launch pricing',
      'Best for active users',
    ],
  },
];

function readErrorDetail(err: unknown): string | undefined {
  if (!err || typeof err !== 'object') return undefined;
  const body = (err as HttpRequestError).body;
  if (!body || typeof body !== 'object') return undefined;
  const detail = (body as { detail?: unknown }).detail;
  return typeof detail === 'string' ? detail : undefined;
}

export default function SubscribePage() {
  const router = useRouter();
  const { status, subscriber, getAccessToken, signOut } = useAuth();
  const [submittingPlan, setSubmittingPlan] = useState<BillingPlan | null>(null);

  // Logged-out users land on signup first (auth before paywall).
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.replace('/signup?next=/subscribe');
    }
  }, [status, router]);

  // Already-subscribed users go straight to the dashboard.
  useEffect(() => {
    if (status === 'authenticated' && subscriber?.has_active_subscription) {
      router.replace('/dashboard');
    }
  }, [status, subscriber, router]);

  async function handleSelectPlan(plan: BillingPlan) {
    const token = getAccessToken();
    if (!token) {
      toast.error('Please sign in to subscribe.');
      router.replace('/login?next=/subscribe');
      return;
    }

    setSubmittingPlan(plan);
    try {
      const { checkout_url } = await createCheckout({ plan }, token);
      // Top-level navigation — Stripe Checkout cannot run inside an iframe.
      window.location.href = checkout_url;
    } catch (err) {
      const detail = readErrorDetail(err);
      if (detail === 'already_subscribed') {
        toast.success('You already have an active subscription.');
        router.replace('/dashboard');
        return;
      }
      if (detail === 'checkout_in_progress') {
        toast.error('A checkout is already in progress. Please wait a moment.');
        return;
      }
      toast.error(
        detail
          ? `Could not start checkout (${detail}).`
          : 'Could not start checkout. Please try again.',
      );
    } finally {
      setSubmittingPlan(null);
    }
  }

  async function handleSignOut() {
    await signOut();
    router.replace('/login');
  }

  if (status === 'loading' || status === 'unauthenticated') {
    return (
      <>
        <LandingHeader />
        <main className="flex flex-1 flex-col items-center justify-center px-4 py-16">
          <LoadingState
            label={
              status === 'loading' ? 'Checking session…' : 'Redirecting…'
            }
          />
        </main>
        <LandingFooter />
      </>
    );
  }

  // status === 'authenticated' (and not yet active — gated above)
  return (
    <>
      <LandingHeader />
      <main className="text-foreground bg-background relative flex flex-1 flex-col items-center px-4 py-12 sm:py-16">
        <div className="w-full max-w-3xl">
          <div className="mb-8 flex flex-col gap-3 text-center sm:mb-12">
            <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
              Choose your plan
            </h1>
            <p className="text-muted mx-auto max-w-xl text-sm leading-relaxed sm:text-base">
              You’re almost there. Pick a plan to unlock the HiddenAlerts
              intelligence dashboard.
            </p>
            {subscriber?.email ? (
              <div className="text-muted mt-2 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-xs">
                <span>
                  Signed in as{' '}
                  <span className="text-foreground">{subscriber.email}</span>
                </span>
                <button
                  type="button"
                  onClick={handleSignOut}
                  className="text-muted hover:text-foreground inline-flex cursor-pointer items-center gap-1 underline-offset-2 hover:underline"
                >
                  <LogOut className="size-3.5" aria-hidden />
                  Sign out
                </button>
              </div>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {PLANS.map(plan => (
              <PlanCard
                key={plan.id}
                plan={plan}
                loading={submittingPlan === plan.id}
                disabled={submittingPlan !== null && submittingPlan !== plan.id}
                onSelect={() => handleSelectPlan(plan.id)}
              />
            ))}
          </div>

          <p className="text-muted mt-6 text-center text-xs leading-relaxed">
            Payments are handled securely by Stripe. You can cancel any time
            from your account settings.
          </p>
        </div>
      </main>
      <LandingFooter />
    </>
  );
}

type PlanCardProps = {
  plan: Plan;
  loading: boolean;
  disabled: boolean;
  onSelect: () => void;
};

function PlanCard({ plan, loading, disabled, onSelect }: PlanCardProps) {
  return (
    <div
      className={cn(
        'border-border bg-surface/70 relative flex flex-col rounded-lg border p-6 backdrop-blur sm:p-7',
        plan.highlighted && 'border-primary-500/50 shadow-md',
      )}
    >
      {plan.badge ? (
        <span className="bg-primary-500/15 text-primary-400 absolute -top-3 right-5 rounded-full px-3 py-0.5 text-[11px] font-semibold tracking-wide uppercase">
          {plan.badge}
        </span>
      ) : null}

      <div className="space-y-1">
        <h2 className="font-heading text-foreground text-lg font-semibold tracking-tight">
          {plan.name}
        </h2>
        <p className="text-muted text-xs leading-relaxed">{plan.description}</p>
      </div>

      <div className="mt-5 flex items-baseline gap-1.5">
        <span className="text-foreground text-3xl font-semibold tracking-tight sm:text-4xl">
          {plan.priceLabel}
        </span>
        <span className="text-muted text-sm">{plan.cadence}</span>
      </div>

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

      <Button
        type="button"
        size="md"
        variant={plan.highlighted ? 'default' : 'outline'}
        loading={loading}
        disabled={disabled}
        onClick={onSelect}
        className="mt-6 w-full"
      >
        {loading ? 'Redirecting to checkout…' : `Subscribe ${plan.name}`}
      </Button>
    </div>
  );
}
