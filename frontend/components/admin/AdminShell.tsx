'use client';

import { Sidebar, type SidebarNavItem } from '@/components/dashboard';
import { useAdminAuth } from '@/contexts/AdminAuthProvider';
import { useSidebar } from '@/hooks/useSidebar';
import { cn } from '@/lib/utils';
import { Bell, FileText, LogOut, Menu, Users } from 'lucide-react';
import { useRouter } from 'next/navigation';
import type { FC, ReactNode } from 'react';

const ADMIN_NAV: SidebarNavItem[] = [
  { href: '/admin/briefs', label: 'Briefs', icon: FileText },
  { href: '/admin/alerts', label: 'Alerts', icon: Bell },
  { href: '/admin/subscribers', label: 'Subscribers', icon: Users },
];

export type AdminShellProps = {
  children: ReactNode;
};

export const AdminShell: FC<AdminShellProps> = ({ children }) => {
  const sidebar = useSidebar();
  const { user, signOut } = useAdminAuth();
  const router = useRouter();

  function handleSignOut() {
    signOut();
    router.replace('/admin/login');
  }

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
        navItems={ADMIN_NAV}
        homeHref="/admin/briefs"
      />

      <div
        className={cn(
          'flex min-h-screen flex-col transition-[padding] duration-200 ease-out',
          'lg:pl-[var(--spacing-sidebar)]',
          sidebar.collapsed && 'lg:pl-[var(--spacing-collapse-sidebar)]',
        )}
      >
        <header className="border-border bg-background-alt sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b px-3 lg:px-5">
          <button
            type="button"
            onClick={sidebar.openMobile}
            className="text-muted hover:text-foreground hover:bg-surface inline-flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-md lg:hidden"
            aria-label="Open menu"
          >
            <Menu className="size-5" />
          </button>

          <div className="ml-auto flex items-center gap-3">
            {user ? (
              <span className="text-muted hidden text-sm sm:inline">
                {user.full_name ?? user.email}
              </span>
            ) : null}
            <button
              type="button"
              onClick={handleSignOut}
              className="text-muted hover:text-foreground hover:bg-surface inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-md px-2.5 text-sm font-medium transition-colors"
              aria-label="Sign out"
            >
              <LogOut className="size-4" aria-hidden />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </header>

        <main className="flex-1 px-3 py-4 sm:px-4 lg:px-6 lg:py-6">
          {children}
        </main>
      </div>
    </div>
  );
};
