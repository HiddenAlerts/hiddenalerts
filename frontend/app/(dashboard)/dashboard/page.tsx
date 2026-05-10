import { DashboardScreen } from '@/components/dashboard';
import { LoadingState } from '@/components/ui/LoadingState';

import type { Metadata } from 'next';
import { Suspense } from 'react';

export const metadata: Metadata = {
  title: 'Dashboard — HiddenAlerts',
};

export default function DashboardHomePage() {
  return (
    <Suspense fallback={<LoadingState label="Loading dashboard…" />}>
      <DashboardScreen />
    </Suspense>
  );
}
