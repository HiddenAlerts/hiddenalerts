import {
  LandingBuiltFor,
  LandingFAQ,
  LandingFooter,
  LandingHeader,
  LandingHero,
  LandingHowItWorks,
  LandingIntelligencePreview,
  LandingPricing,
  LandingSourcesWeMonitor,
} from '@/components/landing';
import { LANDING_LINKS, LANDING_NAV } from '@/data/landing';

export default function Home() {
  return (
    <>
      <LandingHeader
        navItems={LANDING_NAV}
        primaryCta={{
          label: 'Get Free Weekly Intelligence Brief',
          href: LANDING_LINKS.heroSubscribe,
        }}
      />
      <main className="flex flex-1 flex-col">
        <LandingHero />
        <LandingIntelligencePreview />
        <LandingHowItWorks />
        <LandingPricing />
        <LandingSourcesWeMonitor />
        <LandingBuiltFor />
        <LandingFAQ />
      </main>
      <LandingFooter />
    </>
  );
}
