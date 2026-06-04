import { AdminAlertsScreen } from '@/components/admin';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Alerts — HiddenAlerts CMS',
};

export default function AdminAlertsPage() {
  return <AdminAlertsScreen />;
}
