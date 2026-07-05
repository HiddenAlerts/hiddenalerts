import { AdminAlertForm } from '@/components/admin';
import { findAdminAlert } from '@/data/adminMockAlerts';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

type RouteParams = { alertId: string };

export const metadata: Metadata = {
  title: 'Edit Alert — HiddenAlerts CMS',
};

export default async function AdminAlertEditPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { alertId } = await params;
  const alert = findAdminAlert(alertId);
  if (!alert) notFound();

  return (
    <AdminAlertForm
      initial={alert}
      title="Edit Alert"
      subtitle="Update alert"
      returnHref={`/admin/alerts/${alert.id}`}
    />
  );
}
