import { AdminBriefEditScreen } from '@/components/admin';
import { LoadingState } from '@/components/ui/LoadingState';
import type { Metadata } from 'next';
import { Suspense } from 'react';

type RouteParams = { briefId: string };

export const metadata: Metadata = {
  title: 'Edit Brief — HiddenAlerts CMS',
};

export default async function AdminBriefEditPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { briefId } = await params;
  return (
    <Suspense fallback={<LoadingState label="Loading brief…" />}>
      <AdminBriefEditScreen briefId={briefId} />
    </Suspense>
  );
}
