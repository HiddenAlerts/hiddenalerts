'use client';

import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { useSubscriberBriefDetailQuery } from '@/hooks';
import type { HttpRequestError } from '@/lib/api/client';
import { getApiErrorMessage } from '@/lib/api/queryError';
import type { FC } from 'react';

import { BriefReader } from './BriefReader';

export type BriefDetailScreenProps = {
  slug: string;
};

/** Fetches a single published brief by slug and renders it read-only. */
export const BriefDetailScreen: FC<BriefDetailScreenProps> = ({ slug }) => {
  const { data: brief, isPending, isError, error, refetch } =
    useSubscriberBriefDetailQuery(slug);

  if (isPending) {
    return <LoadingState label="Loading brief…" />;
  }

  if (isError) {
    if ((error as HttpRequestError).status === 404) {
      return (
        <EmptyState
          title="Brief not found"
          description="This brief doesn't exist or isn't available to you."
        />
      );
    }
    return (
      <ErrorState
        message={getApiErrorMessage(error, 'Unable to load this brief. Please try again.')}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!brief) {
    return (
      <EmptyState
        title="Brief not found"
        description="This brief doesn't exist or isn't available to you."
      />
    );
  }

  return (
    <div className="border-border bg-background-alt overflow-hidden rounded-xl border">
      <BriefReader brief={brief} topBar="subscriber" />
    </div>
  );
};
