import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Disclaimer — HiddenAlerts',
};

export default function DisclaimerPage() {
  return (
    <main className="bg-background text-foreground mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <h1>Disclaimer</h1>
    </main>
  );
}
