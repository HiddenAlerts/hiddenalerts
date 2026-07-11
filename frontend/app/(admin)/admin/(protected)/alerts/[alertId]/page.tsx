import { AdminAlertDetailScreen } from '@/components/admin';
import type { Metadata } from 'next';

type RouteParams = { alertId: string };

export const metadata: Metadata = {
  title: 'Alert — HiddenAlerts CMS',
};

export default async function AdminAlertDetailPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { alertId } = await params;
  return <AdminAlertDetailScreen alertId={alertId} />;
}
