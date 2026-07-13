'use client';

import { EmptyState, ErrorState, LoadingState } from '@/components';
import { useAdminBriefBySlugQuery } from '@/hooks';
import { getApiErrorMessage } from '@/lib/api/queryError';
import type { FC } from 'react';

import { AdminBriefForm } from './AdminBriefForm';

export type AdminBriefEditScreenProps = {
  slug: string;
};

/** Fetches an existing brief client-side (the admin token lives in the browser) and hands it to `AdminBriefForm`. */
export const AdminBriefEditScreen: FC<AdminBriefEditScreenProps> = ({
  slug,
}) => {
  const { data: brief, isPending, isError, error, refetch } =
    useAdminBriefBySlugQuery(slug);

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
      subtitle="All fields marked with * are required to publish. Drafts only need a title."
      returnHref={`/admin/briefs/${brief.slug}`}
    />
  );
};
