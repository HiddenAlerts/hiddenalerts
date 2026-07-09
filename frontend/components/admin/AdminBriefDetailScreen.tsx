'use client';

import { Button, PageHeader } from '@/components';
import { BriefReader } from '@/components/briefs';
import { findAdminBrief } from '@/data/adminMockBriefs';
import { adminBriefToDetail } from '@/lib/briefDetail';
import { ArrowLeft, Pencil } from 'lucide-react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { FC } from 'react';

export type AdminBriefDetailScreenProps = {
  briefId: string;
};

/**
 * Admin's read view for a single brief. Renders through the same
 * `BriefReader` a subscriber sees, so admins can review published or draft
 * content exactly as it will appear.
 */
export const AdminBriefDetailScreen: FC<AdminBriefDetailScreenProps> = ({
  briefId,
}) => {
  const brief = findAdminBrief(briefId);
  if (!brief) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={brief.title}
        subtitle={`/${brief.slug}`}
        actions={
          <>
            <Link
              href="/admin/briefs"
              className="text-muted hover:text-foreground inline-flex h-9 items-center gap-1.5 px-2 text-sm font-medium"
            >
              <ArrowLeft className="size-4" aria-hidden />
              Back
            </Link>
            <Link href={`/admin/briefs/${brief.id}/edit`}>
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
