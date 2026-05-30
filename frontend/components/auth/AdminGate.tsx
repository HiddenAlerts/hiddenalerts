'use client';

import { LoadingState } from '@/components/ui/LoadingState';
import { useAdminAuth } from '@/contexts/AdminAuthProvider';
import { usePathname, useRouter } from 'next/navigation';
import { type ReactNode, useEffect } from 'react';

/**
 * Wraps the admin tree and:
 *  - shows a loading state while we check `/auth/me`
 *  - redirects to `/login` when there is no valid session
 *  - renders children once the admin is authenticated
 */
export function AdminGate({ children }: { children: ReactNode }) {
  const { status } = useAdminAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status !== 'unauthenticated') return;
    const target = pathname
      ? `/login?next=${encodeURIComponent(pathname)}`
      : '/login';
    router.replace(target);
  }, [status, router, pathname]);

  if (status === 'authenticated') {
    return <>{children}</>;
  }

  return <LoadingState label="Checking access…" />;
}
