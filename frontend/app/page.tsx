import {
  LandingFAQ,
  LandingFeatureHighlights,
  LandingFooter,
  LandingHeader,
  LandingHero,
  LandingHowItWorks,
  LandingIntelligencePreview,
  LandingNewsletterCta,
  LandingPricing,
  LandingProblem,
  LandingTrustBar,
} from '@/components/landing';
import { LANDING_LINKS, LANDING_NAV } from '@/data/landing';

export default function Home() {
  return (
    <>
      <LandingHeader
        navItems={LANDING_NAV}
        primaryCta={{ label: 'Get Early Access', href: LANDING_LINKS.signup }}
      />
      <main className="flex flex-1 flex-col">
        <LandingHero />
        <LandingFeatureHighlights />
        <LandingProblem />
        <LandingIntelligencePreview />
        <LandingHowItWorks />
        <LandingNewsletterCta />
        <LandingPricing />
        <LandingTrustBar />
        <LandingFAQ />
      </main>
      <LandingFooter />
    </>
  );
}
