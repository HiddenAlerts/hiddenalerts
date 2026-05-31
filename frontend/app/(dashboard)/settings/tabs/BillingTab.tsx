'use client';

import { Button } from '@/components/ui/button';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/contexts/AuthProvider';
import { createCustomerPortal, fetchBillingStatus } from '@/lib/api/billing';
import type { HttpRequestError } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import type { BillingStatusResponse } from '@/types/billing';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState, type FC } from 'react';
import { toast } from 'sonner';

const STATUS_TONE: Record<string, string> = {
  active: 'bg-success-500/15 text-success-400',
  trialing: 'bg-success-500/15 text-success-400',
  past_due: 'bg-warning-500/15 text-warning-400',
  unpaid: 'bg-warning-500/15 text-warning-400',
  canceled: 'bg-danger-500/15 text-danger-400',
  incomplete: 'bg-muted/15 text-muted',
  incomplete_expired: 'bg-muted/15 text-muted',
};

function formatStatusLabel(status: string | null | undefined): string {
  if (!status) return 'No subscription';
  return status.replace(/_/g, ' ');
}

function formatPlanLabel(plan: string | null | undefined): string {
  if (!plan) return 'No plan';
  return plan.charAt(0).toUpperCase() + plan.slice(1);
}

function formatDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export const BillingTab: FC = () => {
  const { getAccessToken } = useAuth();
  const router = useRouter();
  const token = getAccessToken();

  const [openingPortal, setOpeningPortal] = useState(false);

  const billingQuery = useQuery<BillingStatusResponse, HttpRequestError>({
    queryKey: ['billing-status'],
    queryFn: () => fetchBillingStatus(token!),
    enabled: Boolean(token),
  });

  async function handleOpenPortal() {
    if (!token || openingPortal) return;

    // Open the tab synchronously inside the click handler — popup blockers
    // would otherwise reject an `open()` that runs after an `await`.
    const portalTab = window.open('', '_blank');

    setOpeningPortal(true);
    try {
      const { portal_url } = await createCustomerPortal(token);
      if (portalTab) {
        // Drop the back-reference to this window before navigating to Stripe.
        portalTab.opener = null;
        portalTab.location.href = portal_url;
      } else {
        // Popup was blocked — same-tab fallback so the user still reaches Stripe.
        window.location.href = portal_url;
      }
    } catch {
      portalTab?.close();
      toast.error('Could not open the billing portal. Please try again.');
    } finally {
      setOpeningPortal(false);
    }
  }

  if (!token || billingQuery.isPending) {
    return <LoadingState label="Loading billing details…" />;
  }

  if (billingQuery.isError) {
    return (
      <ErrorState
        title="Could not load billing"
        message="We could not load your subscription details. Please try again."
        onRetry={() => billingQuery.refetch()}
      />
    );
  }

  const data = billingQuery.data;
  const hasRecord = Boolean(data.subscription_status);
  const renewalDate = formatDate(data.current_period_end);
  const statusKey = data.subscription_status ?? '';
  const statusTone =
    STATUS_TONE[statusKey] ?? 'bg-muted/15 text-muted';

  return (
    <div className="space-y-4">
      <div className="border-border bg-background-alt rounded-lg border p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <h2 className="text-foreground text-base font-semibold">
              Subscription
            </h2>
            <p className="text-muted text-sm">
              {hasRecord
                ? 'Your current plan and renewal information.'
                : 'You do not have an active subscription yet.'}
            </p>
          </div>

          <span
            className={cn(
              'inline-flex h-7 shrink-0 items-center rounded-full px-3 text-xs font-semibold tracking-wide capitalize',
              statusTone,
            )}
          >
            {formatStatusLabel(data.subscription_status)}
          </span>
        </div>

        <dl className="border-border mt-5 grid grid-cols-1 gap-4 border-t pt-5 sm:grid-cols-2">
          <DetailRow label="Plan" value={formatPlanLabel(data.plan_type)} />
          <DetailRow
            label={data.cancel_at_period_end ? 'Ends on' : 'Next renewal'}
            value={renewalDate ?? '—'}
          />
        </dl>

        {data.cancel_at_period_end && renewalDate ? (
          <p className="bg-warning-500/10 text-warning-300 mt-5 rounded-md px-3 py-2 text-xs">
            Your subscription is scheduled to end on {renewalDate}. You can
            resume it from the billing portal.
          </p>
        ) : null}

        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
          {hasRecord ? (
            <Button
              type="button"
              variant="default"
              loading={openingPortal}
              onClick={handleOpenPortal}
              rightIcon={
                openingPortal ? null : (
                  <ExternalLink className="size-4" aria-hidden />
                )
              }
            >
              Manage subscription
            </Button>
          ) : (
            <Button
              type="button"
              variant="default"
              onClick={() => router.push('/subscribe')}
            >
              Choose a plan
            </Button>
          )}
        </div>
      </div>

      <p className="text-muted text-xs">
        Payments and invoices are managed securely by Stripe.
      </p>
    </div>
  );
};

type DetailRowProps = {
  label: string;
  value: string;
};

function DetailRow({ label, value }: DetailRowProps) {
  return (
    <div className="space-y-1">
      <dt className="text-muted text-xs font-medium tracking-wide uppercase">
        {label}
      </dt>
      <dd className="text-foreground text-sm">{value}</dd>
    </div>
  );
}
