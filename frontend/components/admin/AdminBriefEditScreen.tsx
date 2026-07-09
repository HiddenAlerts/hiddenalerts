'use client';

import { EmptyState, ErrorState, LoadingState } from '@/components';
import { useAdminBriefDetailQuery } from '@/hooks';
import { getApiErrorMessage } from '@/lib/api/queryError';
import type { FC } from 'react';

import { AdminBriefForm } from './AdminBriefForm';

export type AdminBriefEditScreenProps = {
  briefId: string;
};

/** Fetches an existing brief client-side (the admin token lives in the browser) and hands it to `AdminBriefForm`. */
export const AdminBriefEditScreen: FC<AdminBriefEditScreenProps> = ({
  briefId,
}) => {
  const { data: brief, isPending, isError, error, refetch } =
    useAdminBriefDetailQuery(briefId);

  if (isPending) {
    return <LoadingState label="Loading brief…" />;
  }

  if (isError) {
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
        description="This brief is not available right now."
      />
    );
  }

  return (
    <AdminBriefForm
      initial={brief}
      title="Edit Intelligence Brief"
      subtitle="All fields marked with * are required."
      returnHref={`/admin/briefs/${brief.id}`}
    />
  );
};
