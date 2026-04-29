import { AlertDetailScreen } from '@/components/alerts/AlertDetailScreen';
import type { Metadata } from 'next';

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
  return <AlertDetailScreen alertId={alertId} />;
}
