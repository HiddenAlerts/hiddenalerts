import { AdminSubscribersScreen } from '@/components/admin';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Subscribers — HiddenAlerts CMS',
};

export default function AdminSubscribersPage() {
  return <AdminSubscribersScreen />;
}
