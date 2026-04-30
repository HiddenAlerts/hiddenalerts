import { AlertsScreen } from '@/components/alerts';
import { LoadingState } from '@/components/ui/LoadingState';
import type { Metadata } from 'next';
import { Suspense } from 'react';

export const metadata: Metadata = {
  title: 'Alerts — HiddenAlerts',
  description: 'View and filter intelligence alerts.',
};

export default function AlertsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading alerts…" />}>
      <AlertsScreen />
    </Suspense>
  );
}
