'use client';

import type { HttpRequestError } from '@/lib/api/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

type QueryProviderProps = {
  children: ReactNode;
};

/**
 * Errors that will never recover from a retry — token problems, missing
 * permissions, missing resources. We surface these to the UI immediately
 * instead of leaving the query in a "loading" state for several seconds.
 */
const NO_RETRY_STATUSES = new Set([400, 401, 403, 404, 422]);

function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  const status = (error as HttpRequestError)?.status;
  if (typeof status === 'number' && NO_RETRY_STATUSES.has(status)) {
    return false;
  }
  return failureCount < 2;
}

export function QueryProvider({ children }: QueryProviderProps) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            refetchOnWindowFocus: true,
            retry: shouldRetryQuery,
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
