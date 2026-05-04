'use client';

import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  MonitorDot,
  PanelLeft,
  PanelLeftClose,
  Settings,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { FC } from 'react';

const nav = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/alerts', label: 'Alerts', icon: MonitorDot },
  { href: '/settings', label: 'Settings (Coming Soon)', icon: Settings },
] as const;

export type SidebarProps = {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
};

export const Sidebar: FC<SidebarProps> = ({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}) => {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        'border-border bg-background-alt fixed inset-y-0 left-0 z-40 flex w-[var(--spacing-sidebar)] flex-col border-r transition-all duration-200 ease-out',
        'lg:translate-x-0',
        mobileOpen ? 'translate-x-0' : '-translate-x-full',
        collapsed && 'lg:w-[var(--spacing-collapse-sidebar)]',
      )}
      aria-label="Main navigation"
    >
      <div
        className={cn(
          'border-border flex shrink-0 items-center border-b px-3',
          'h-14 gap-2',
          collapsed
            ? 'justify-center lg:h-auto lg:min-h-14 lg:flex-col lg:justify-center lg:gap-2 lg:px-1 lg:py-2.5'
            : 'justify-between',
        )}
      >
        <Link
          href="/dashboard"
          onClick={onCloseMobile}
          className={cn(
            'text-foreground inline-flex min-w-0 cursor-pointer items-center gap-2 font-semibold',
            collapsed && 'lg:w-full lg:min-w-0 lg:justify-center',
          )}
        >
          <span className="bg-primary-500/15 text-primary-500 inline-flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-md p-0.5">
            <img
              src="/images/logo-symbol.png"
              alt=""
              width={36}
              height={36}
              className="size-full object-contain"
              decoding="async"
            />
          </span>
          <span
            className={cn(
              'font-heading truncate text-base tracking-tight',
              'lg:transition-opacity',
              collapsed && 'lg:sr-only',
            )}
          >
            HiddenAlerts
          </span>
        </Link>

        <button
          type="button"
          onClick={onToggleCollapse}
          className={cn(
            'text-muted hover:text-foreground hover:bg-surface hidden size-9 shrink-0 cursor-pointer items-center justify-center rounded-md transition-colors lg:inline-flex',
          )}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeft className="size-5" aria-hidden />
          ) : (
            <PanelLeftClose className="size-5" aria-hidden />
          )}
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-2">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              onClick={onCloseMobile}
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors',
                'lg:justify-start',
                collapsed && 'lg:justify-center lg:px-0',
                active
                  ? 'bg-primary-500 text-white'
                  : 'text-muted hover:bg-surface hover:text-foreground',
              )}
            >
              <Icon className="size-5 shrink-0" aria-hidden />
              <span className={cn(collapsed && 'lg:sr-only')}>{label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
};
