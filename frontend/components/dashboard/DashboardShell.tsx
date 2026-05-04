'use client';

import { useSidebar } from '@/hooks/useSidebar';
import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export type DashboardShellProps = {
  children: ReactNode;
};

export const DashboardShell: FC<DashboardShellProps> = ({ children }) => {
  const sidebar = useSidebar();

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
        <TopBar onOpenSidebar={sidebar.openMobile} />
        <main className="flex-1 px-3 py-4 sm:px-4 lg:px-6 lg:py-6">
          {children}
        </main>
      </div>
    </div>
  );
};
