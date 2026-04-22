import {
  LandingContentSections,
  LandingFAQ,
  LandingFooter,
  LandingHeader,
  LandingHero,
} from '@/components/landing';

export default function Home() {
  return (
    <>
      <LandingHeader />
      <main className="flex flex-1 flex-col">
        <LandingHero />
        <LandingContentSections />
        <LandingFAQ />
      </main>
      <LandingFooter />
    </>
  );
}
