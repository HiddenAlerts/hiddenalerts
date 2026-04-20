import { DashboardScreen } from '@/components/dashboard';

import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Dashboard — HiddenAlerts',
};

export default function DashboardHomePage() {
  return <DashboardScreen />;
}
