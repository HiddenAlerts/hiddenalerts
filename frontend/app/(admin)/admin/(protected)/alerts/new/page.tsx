import { AdminAlertForm } from '@/components/admin';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'New Alert — HiddenAlerts CMS',
};

export default function AdminAlertNewPage() {
  return (
    <AdminAlertForm
      title="Create Alert"
      subtitle="Add a new alert"
      returnHref="/admin/alerts"
    />
  );
}
