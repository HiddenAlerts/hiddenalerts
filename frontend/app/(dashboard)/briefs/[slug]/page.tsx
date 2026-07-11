import { BriefDetailScreen } from '@/components/briefs';
import { LoadingState } from '@/components/ui/LoadingState';
import type { Metadata } from 'next';
import { Suspense } from 'react';

type RouteParams = { slug: string };

export const metadata: Metadata = {
  title: 'Intelligence Brief — HiddenAlerts',
};

export default async function BriefDetailPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { slug } = await params;
  return (
    <Suspense fallback={<LoadingState label="Loading brief…" />}>
      <BriefDetailScreen slug={slug} />
    </Suspense>
  );
}
