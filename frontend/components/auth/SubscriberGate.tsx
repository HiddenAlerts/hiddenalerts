'use client';

import { LoadingState } from '@/components/ui/LoadingState';
import { useAuth } from '@/contexts/AuthProvider';
import { usePathname, useRouter } from 'next/navigation';
import { type ReactNode, useEffect } from 'react';

export function SubscriberGate({ children }: { children: ReactNode }) {
  const { status } = useAuth();
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
