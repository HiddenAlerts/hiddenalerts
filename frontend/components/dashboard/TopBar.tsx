'use client';

import {
  AlertsSearchForm,
  AlertsSearchFormFallback,
} from '@/components/alerts/AlertsSearchForm';
import { Avatar } from '@/components';
import { cn } from '@/lib/utils';
import { Bell, ChevronDown, Menu } from 'lucide-react';
import type { FC } from 'react';
import { Suspense } from 'react';

export type TopBarProps = {
  onOpenSidebar: () => void;
  className?: string;
  /**
   * When false, the alerts search field is omitted (shown elsewhere, e.g. under the header on small screens).
   */
  showAlertsSearch?: boolean;
};

export const TopBar: FC<TopBarProps> = ({
  onOpenSidebar,
  className,
  showAlertsSearch = true,
}) => (
  <header
    className={cn(
      'border-border bg-background-alt sticky top-0 z-30 flex min-h-14 shrink-0 items-center gap-2 border-b px-3 py-1.5 sm:gap-3 lg:h-14 lg:px-5 lg:py-0',
      className,
    )}
  >
    <button
      type="button"
      onClick={onOpenSidebar}
      className="text-muted hover:text-foreground hover:bg-surface inline-flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-md lg:hidden"
      aria-label="Open menu"
    >
      <Menu className="size-5" />
    </button>

    {showAlertsSearch ? (
      <div className="flex min-w-0 flex-1 items-center md:max-w-xl lg:max-w-2xl">
        <Suspense fallback={<AlertsSearchFormFallback />}>
          <AlertsSearchForm />
        </Suspense>
      </div>
    ) : (
      <div className="min-w-0 flex-1 md:hidden" aria-hidden />
    )}

    <div className="ml-auto flex shrink-0 items-center gap-1 sm:gap-2">
      <button
        type="button"
        className="text-muted hover:text-foreground hover:bg-surface inline-flex size-10 cursor-pointer items-center justify-center rounded-md"
        aria-label="Notifications"
      >
        <Bell className="size-5" />
      </button>

      <button
        type="button"
        className="hover:bg-surface inline-flex cursor-pointer items-center gap-1 rounded-md py-1 pr-1 pl-1 sm:pr-2"
        aria-label="Account menu"
      >
        <Avatar size="sm" alt="Account" />
        <ChevronDown className="text-muted hidden size-4 sm:block" aria-hidden />
      </button>
    </div>
  </header>
);
