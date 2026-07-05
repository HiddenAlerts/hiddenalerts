'use client';

import {
  AlertsSearchForm,
  AlertsSearchFormFallback,
} from '@/components/alerts/AlertsSearchForm';
import { useMinMd } from '@/hooks/useMinMd';
import { useSidebar } from '@/hooks/useSidebar';
import { cn } from '@/lib/utils';
import { usePathname } from 'next/navigation';
import type { FC, ReactNode } from 'react';
import { Suspense, useEffect, useState } from 'react';

import { DashboardFooter } from './DashboardFooter';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export type DashboardShellProps = {
  children: ReactNode;
};

export const DashboardShell: FC<DashboardShellProps> = ({ children }) => {
  const sidebar = useSidebar();
  const pathname = usePathname();
  const mqMdUp = useMinMd();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const id = window.setTimeout(() => setMounted(true), 0);
    return () => window.clearTimeout(id);
  }, []);

  const isAlertsRoute = pathname === '/alerts';
  const isDashboardRoute = pathname === '/dashboard';
  // The dashboard renders its own search field inline, so hide it in the top bar.
  const topBarShowsSearch =
    !isDashboardRoute && (!isAlertsRoute || !mounted || mqMdUp);

  const showMobileAlertsSearch =
    isAlertsRoute && mounted && !mqMdUp;

  return (
    <div className="bg-background text-foreground min-h-screen">
      {sidebar.mobileOpen ? (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-30 cursor-pointer bg-black/50 lg:hidden"
          onClick={sidebar.closeMobile}
        />
      ) : null}

      <Sidebar
        collapsed={sidebar.collapsed}
        onToggleCollapse={sidebar.toggleCollapse}
        mobileOpen={sidebar.mobileOpen}
        onCloseMobile={sidebar.closeMobile}
      />

      <div
        className={cn(
          'flex min-h-screen flex-col transition-[padding] duration-200 ease-out',
          'lg:pl-[var(--spacing-sidebar)]',
          sidebar.collapsed && 'lg:pl-[var(--spacing-collapse-sidebar)]',
        )}
      >
        <TopBar
          onOpenSidebar={sidebar.openMobile}
          showAlertsSearch={topBarShowsSearch}
        />

        {showMobileAlertsSearch ? (
          <section
            className="border-border bg-background-alt md:hidden border-b px-3 pb-3 pt-2 sm:px-4"
            aria-label="Search alerts"
          >
            <Suspense fallback={<AlertsSearchFormFallback className="w-full" />}>
              <AlertsSearchForm className="w-full" />
            </Suspense>
          </section>
        ) : null}

        <main className="flex-1 px-3 py-4 sm:px-4 lg:px-6 lg:py-6">
          {children}
        </main>
        <DashboardFooter />
      </div>
    </div>
  );
};
