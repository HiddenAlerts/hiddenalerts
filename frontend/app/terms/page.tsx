import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Terms of Use — HiddenAlerts',
};

export default function TermsPage() {
  return (
    <main className="bg-background text-foreground mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <h1>Terms of Use</h1>
    </main>
  );
}
