import { AdminAlertDetailScreen } from '@/components/admin';
import { findAdminAlert } from '@/data/adminMockAlerts';
import type { Metadata } from 'next';

type RouteParams = { alertId: string };

export async function generateMetadata({
  params,
}: {
  params: Promise<RouteParams>;
}): Promise<Metadata> {
  const { alertId } = await params;
  const alert = findAdminAlert(alertId);
  return {
    title: alert
      ? `${alert.title} — HiddenAlerts CMS`
      : 'Alert — HiddenAlerts CMS',
  };
}

export default async function AdminAlertDetailPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { alertId } = await params;
  return <AdminAlertDetailScreen alertId={alertId} />;
}
