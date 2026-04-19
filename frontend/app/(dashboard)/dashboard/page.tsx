import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Dashboard — HiddenAlerts',
};

export default function DashboardHomePage() {
  return (
    <div className="space-y-4">
      <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight">
        Dashboard
      </h1>
      <p className="text-muted text-sm">
        Overview content will live here. Open{' '}
        <Link
          href="/alerts"
          className="text-primary-400 hover:text-primary-300 font-medium underline-offset-2 hover:underline"
        >
          Alerts
        </Link>{' '}
        to see the table and filters.
      </p>
    </div>
  );
}
