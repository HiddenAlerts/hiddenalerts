'use client';

import { LoadingState } from '@/components/ui/LoadingState';
import { useAdminAuth } from '@/contexts/AdminAuthProvider';
import { usePathname, useRouter } from 'next/navigation';
import { type ReactNode, useEffect, useRef } from 'react';

/**
 * Wraps the admin tree and:
 *  - shows a loading state while we check `/auth/me`
 *  - redirects to `/admin/login` when there is no valid session
 *  - renders children once the admin is authenticated
 */
export function AdminGate({ children }: { children: ReactNode }) {
  const { status } = useAdminAuth();
  const router = useRouter();
  const pathname = usePathname();
  // Tracks whether this gate ever saw an authenticated session. Used to tell a
  // genuine deep-link (never authenticated → keep `next`) apart from a logout or
  // expiry (was authenticated → send to a clean `/admin/login`).
  const wasAuthenticated = useRef(false);

  useEffect(() => {
    if (status === 'authenticated') {
      wasAuthenticated.current = true;
      return;
    }
    if (status !== 'unauthenticated') return;
    const target =
      !wasAuthenticated.current && pathname
        ? `/admin/login?next=${encodeURIComponent(pathname)}`
        : '/admin/login';
    router.replace(target);
  }, [status, router, pathname]);

  if (status === 'authenticated') {
    return <>{children}</>;
  }

  return <LoadingState label="Checking access…" />;
}
