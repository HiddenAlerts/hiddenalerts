import { AdminBriefEditScreen } from '@/components/admin';
import { LoadingState } from '@/components/ui/LoadingState';
import type { Metadata } from 'next';
import { Suspense } from 'react';

type RouteParams = { slug: string };

export const metadata: Metadata = {
  title: 'Edit Brief — HiddenAlerts CMS',
};

export default async function AdminBriefEditPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { slug } = await params;
  return (
    <Suspense fallback={<LoadingState label="Loading brief…" />}>
      <AdminBriefEditScreen slug={slug} />
    </Suspense>
  );
}
