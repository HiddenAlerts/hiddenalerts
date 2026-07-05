import { AlertDetailScreen } from '@/components/alerts/AlertDetailScreen';
import { LoadingState } from '@/components/ui/LoadingState';
import type { Metadata } from 'next';
import { Suspense } from 'react';

export const metadata: Metadata = {
  title: 'Alert Detail — HiddenAlerts',
  description: 'Detailed signal intelligence view.',
};

export default async function AlertDetailPage({
  params,
}: {
  params: Promise<{ alertId: string }>;
}) {
  const { alertId } = await params;
  return (
    <Suspense fallback={<LoadingState label="Loading alert…" />}>
      <AlertDetailScreen alertId={alertId} />
    </Suspense>
  );
}
