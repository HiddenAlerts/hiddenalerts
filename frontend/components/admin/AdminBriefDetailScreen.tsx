'use client';

import { Button, EmptyState, ErrorState, LoadingState, PageHeader } from '@/components';
import { BriefReader } from '@/components/briefs';
import { useAdminBriefBySlugQuery } from '@/hooks';
import { getApiErrorMessage } from '@/lib/api/queryError';
import { adminBriefToDetail } from '@/lib/briefDetail';
import { ArrowLeft, Pencil } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

export type AdminBriefDetailScreenProps = {
  slug: string;
};

/**
 * Admin's read view for a single brief. Renders through the same
 * `BriefReader` a subscriber sees, so admins can review published or draft
 * content exactly as it will appear.
 */
export const AdminBriefDetailScreen: FC<AdminBriefDetailScreenProps> = ({
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
    <div className="space-y-6">
      <PageHeader
        title={brief.title}
        subtitle={`${brief.briefCode} · /${brief.slug}`}
        actions={
          <>
            <Link
              href="/admin/briefs"
              className="text-muted hover:text-foreground inline-flex h-9 items-center gap-1.5 px-2 text-sm font-medium"
            >
              <ArrowLeft className="size-4" aria-hidden />
              Back
            </Link>
            <Link href={`/admin/briefs/${brief.slug}/edit`}>
              <Button
                type="button"
                size="sm"
                leftIcon={<Pencil className="size-4" aria-hidden />}
              >
                Edit
              </Button>
            </Link>
          </>
        }
      />

      <div className="border-border bg-background-alt overflow-hidden rounded-lg border">
        <BriefReader brief={adminBriefToDetail(brief)} topBar="none" />
      </div>
    </div>
  );
};
