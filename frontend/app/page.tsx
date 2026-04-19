import type { Metadata } from 'next';

import {
  LandingDashboardPreview,
  LandingFAQ,
  LandingFooter,
  LandingHeader,
  LandingHero,
} from '@/components/landing';

export const metadata: Metadata = {
  title: 'HiddenAlerts — Fraud intelligence, early',
  description:
    'Signals before the headlines. Join the waitlist for early fraud and financial threat alerts from curated sources.',
};

export default function Home() {
  return (
    <>
      <LandingHeader />
      <main className="flex flex-1 flex-col">
        <LandingHero />
        <LandingDashboardPreview />
        <LandingFAQ />
      </main>
      <LandingFooter />
    </>
  );
}
