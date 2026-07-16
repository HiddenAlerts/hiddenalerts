import {
  LandingFAQ,
  LandingFooter,
  LandingHeader,
  LandingHero,
  LandingHowItWorks,
  LandingIntelligencePreview,
  LandingPricing,
  LandingSourcesWeMonitor,
  LandingValueProps,
} from '@/components/landing';
import { LANDING_LINKS, LANDING_NAV } from '@/data/landing';

export default function Home() {
  return (
    <>
      <LandingHeader
        navItems={LANDING_NAV}
        primaryCta={{
          label: 'Join Free Intelligence Updates',
          href: LANDING_LINKS.heroSubscribe,
        }}
      />
      <main className="flex flex-1 flex-col">
        <LandingHero />
        <LandingValueProps />
        <LandingIntelligencePreview />
        <LandingHowItWorks />
        <LandingPricing />
        <LandingSourcesWeMonitor />
        <LandingFAQ />
      </main>
      <LandingFooter />
    </>
  );
}
