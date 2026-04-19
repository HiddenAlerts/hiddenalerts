import { AlertsScreen } from '@/components/alerts';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Alerts — HiddenAlerts',
  description: 'View and filter intelligence alerts.',
};

export default function AlertsPage() {
  return <AlertsScreen />;
}
