'use client';

import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/contexts/AuthProvider';
import { usePathname, useRouter } from 'next/navigation';
import { type ReactNode, useEffect } from 'react';

/**
 * Protects subscriber dashboard routes.
 *  - unauthenticated → redirect to /login
 *  - authenticated, no active subscription → redirect to /subscribe
 *  - authenticated, active subscription → render children
 *
 * Paths in `SUBSCRIPTION_OPTIONAL_PATHS` are exempt from the paywall — the
 * user only needs to be signed in. Account-management pages live here so a
 * locked user can still manage / cancel / update their account.
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

  const locked =
    status === 'authenticated' &&
    subscriber?.has_active_subscription === false &&
    pathRequiresSubscription(pathname);

  useEffect(() => {
    if (status === 'unauthenticated') {
      const target = pathname
        ? `/login?next=${encodeURIComponent(pathname)}`
        : '/login';
      router.replace(target);
      return;
    }
    if (locked) {
      router.replace('/subscribe');
    }
  }, [status, locked, router, pathname]);

  if (status === 'loading' || status === 'unauthenticated' || locked) {
    return (
      <LoadingState
        label={locked ? 'Redirecting to subscription…' : 'Checking access…'}
      />
    );
  }

  return <>{children}</>;
}
