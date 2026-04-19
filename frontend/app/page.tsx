import {
  LandingDashboardPreview,
  LandingFAQ,
  LandingFooter,
  LandingHeader,
  LandingHero,
} from '@/components/landing';
import { useState } from 'react';

export default function Home() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!email) return;
    console.log('Captured email:', email); // temporary
    setSubmitted(true);
  };

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
