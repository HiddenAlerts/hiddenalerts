import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Design system — HiddenAlerts',
  description: 'Design system and component previews for HiddenAlerts.',
};

export default function DesignSystemPage() {
  return (
    <main className="mx-auto min-h-full max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="border-border space-y-2 border-b pb-8">
        <p className="caption">HiddenAlerts · internal</p>
        <h1>Design system</h1>
        <p className="text-muted max-w-2xl">
          Component previews will live here.
        </p>
      </header>
    </main>
  );
}
