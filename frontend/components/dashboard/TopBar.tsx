'use client';

import { Avatar, Input } from '@/components';
import { cn } from '@/lib/utils';
import { Bell, ChevronDown, Menu, Search } from 'lucide-react';
import type { FC } from 'react';

export type TopBarProps = {
  onOpenSidebar: () => void;
  className?: string;
};

export const TopBar: FC<TopBarProps> = ({ onOpenSidebar, className }) => (
  <header
    className={cn(
      'border-border bg-background-alt sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b px-3 lg:px-5',
      className,
    )}
  >
    <button
      type="button"
      onClick={onOpenSidebar}
      className="text-muted hover:text-foreground hover:bg-surface inline-flex size-10 items-center justify-center rounded-md lg:hidden"
      aria-label="Open menu"
    >
      <Menu className="size-5" />
    </button>

    <div className="hidden min-w-0 flex-1 md:block md:max-w-xl lg:max-w-2xl">
      <Input
        type="search"
        name="alert-search"
        placeholder="Search alerts"
        leftIcon={<Search />}
        inputSize="sm"
        className="h-10"
        aria-label="Search alerts"
      />
    </div>

    <div className="min-w-0 flex-1 md:hidden" aria-hidden />

    <div className="ml-auto flex items-center gap-1 sm:gap-2">
      <button
        type="button"
        className="text-muted hover:text-foreground hover:bg-surface inline-flex size-10 items-center justify-center rounded-md"
        aria-label="Notifications"
      >
        <Bell className="size-5" />
      </button>

      <button
        type="button"
        className="hover:bg-surface inline-flex items-center gap-1 rounded-md py-1 pr-1 pl-1 sm:pr-2"
        aria-label="Account menu"
      >
        <Avatar size="sm" alt="Account" />
        <ChevronDown className="text-muted hidden size-4 sm:block" aria-hidden />
      </button>
    </div>
  </header>
);
