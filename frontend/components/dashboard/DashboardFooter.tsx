import Link from 'next/link';
import type { FC } from 'react';

export const DashboardFooter: FC = () => {
  const linkClassName =
    'text-body hover:text-foreground focus-visible:ring-primary-500 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none';

  return (
    <footer
      className="border-border-subtle shrink-0 border-t px-3 py-4 sm:px-4 lg:px-6"
      aria-label="Legal"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-x-6 sm:gap-y-2">
        <p className="text-muted-foreground text-sm">
          HiddenAlerts is a product of{' '}
          <strong className="text-foreground font-bold">Covertlytics, LLC.</strong>
        </p>
        <nav
          className="flex flex-wrap gap-x-4 gap-y-1"
          aria-label="Legal links"
        >
          <Link href="/disclaimer" className={linkClassName}>
            Disclaimer
          </Link>
          <Link href="/terms" className={linkClassName}>
            Terms of Use
          </Link>
          <Link href="/privacy" className={linkClassName}>
            Privacy Policy
          </Link>
        </nav>
      </div>
    </footer>
  );
};
