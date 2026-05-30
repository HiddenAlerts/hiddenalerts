'use client';

import { Button } from '@/components/ui/button';
import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/contexts/AuthProvider';
import { Lock } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { type ReactNode, useEffect } from 'react';

/**
 * Protects subscriber dashboard routes. Three states:
 *  - unauthenticated → redirect to /login
 *  - authenticated, no active subscription → show paywall notice
 *  - authenticated, active subscription → render children
 *
 * Paths in `SUBSCRIPTION_OPTIONAL_PATHS` are exempt from the paywall — the
 * user only needs to be signed in. Account-management pages live here so
 * a locked user can still manage / cancel / update their account.
 */
const SUBSCRIPTION_OPTIONAL_PATHS: readonly string[] = ['/settings'];

function pathRequiresSubscription(pathname: string | null): boolean {
  if (!pathname) return true;
  return !SUBSCRIPTION_OPTIONAL_PATHS.some(
    p => pathname === p || pathname.startsWith(`${p}/`),
  );
}

export function SubscriberGate({ children }: { children: ReactNode }) {
  const { status, subscriber } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status !== 'unauthenticated') return;
    const target = pathname
      ? `/login?next=${encodeURIComponent(pathname)}`
      : '/login';
    router.replace(target);
  }, [status, router, pathname]);

  if (status === 'loading' || status === 'unauthenticated') {
    return <LoadingState label="Checking access…" />;
  }

  // Authenticated. Block when backend says the user is locked, but allow
  // account-management pages (e.g. /settings) so users can still manage
  // their account before subscribing.
  if (
    subscriber &&
    subscriber.has_active_subscription === false &&
    pathRequiresSubscription(pathname)
  ) {
    return <SubscriptionRequiredNotice email={subscriber.email} />;
  }

  return <>{children}</>;
}

function SubscriptionRequiredNotice({ email }: { email: string }) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <div className="border-border bg-background-alt mx-auto max-w-md rounded-lg border p-8 text-center">
        <div className="bg-primary-500/10 text-primary-400 mx-auto flex size-12 items-center justify-center rounded-full">
          <Lock className="size-5" aria-hidden />
        </div>
        <h2 className="font-heading text-foreground mt-4 text-xl font-semibold tracking-tight">
          Subscription required
        </h2>
        <p className="text-muted mt-2 text-sm leading-relaxed">
          You’re signed in as <span className="text-foreground">{email}</span>,
          but your account doesn’t have an active subscription yet. Subscribe
          to unlock alerts, search, and the full intelligence dashboard.
        </p>
        <div className="mt-6">
          <Link href="/subscribe">
            <Button type="button" size="md" className="w-full">
              Subscribe to continue
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
