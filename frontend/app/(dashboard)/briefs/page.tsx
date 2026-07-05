import { BriefsLibraryScreen } from '@/components/briefs';
import { LoadingState } from '@/components/ui/LoadingState';
import type { Metadata } from 'next';
import { Suspense } from 'react';

export const metadata: Metadata = {
  title: 'Intelligence Briefs — HiddenAlerts',
  description:
    'Curated intelligence briefs on emerging threats, criminal methodologies, cyber threats, and national security risks.',
};

export default function BriefsLibraryPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading intelligence briefs…" />}>
      <BriefsLibraryScreen />
    </Suspense>
  );
}
