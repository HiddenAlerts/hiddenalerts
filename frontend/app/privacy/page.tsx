import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Privacy Policy — HiddenAlerts',
};

export default function PrivacyPage() {
  return (
    <main className="bg-background text-foreground mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <h1>Privacy Policy</h1>
    </main>
  );
}
