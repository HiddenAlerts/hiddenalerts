'use client';

import { PageHeader } from '@/components/ui/PageHeader';
import { cn } from '@/lib/utils';
import { type FC, useState } from 'react';

import { BillingTab } from './tabs/BillingTab';
import { PasswordTab } from './tabs/PasswordTab';
import { ProfileTab } from './tabs/ProfileTab';

const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'password', label: 'Change password' },
  { id: 'billing', label: 'Billing' },
] as const;

type TabId = (typeof TABS)[number]['id'];

export const SettingsView: FC = () => {
  const [active, setActive] = useState<TabId>('profile');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        subtitle="Manage your profile, security, and subscription."
      />

      <div
        role="tablist"
        aria-label="Settings sections"
        className="border-border flex flex-wrap gap-1 border-b"
      >
        {TABS.map(tab => {
          const isActive = tab.id === active;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`settings-panel-${tab.id}`}
              id={`settings-tab-${tab.id}`}
              onClick={() => setActive(tab.id)}
              className={cn(
                'relative -mb-px cursor-pointer px-3 py-2.5 text-sm font-medium transition-colors',
                'border-b-2',
                isActive
                  ? 'border-primary-500 text-foreground'
                  : 'text-muted hover:text-foreground border-transparent',
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div
        role="tabpanel"
        id={`settings-panel-${active}`}
        aria-labelledby={`settings-tab-${active}`}
      >
        {active === 'profile' ? <ProfileTab /> : null}
        {active === 'password' ? <PasswordTab /> : null}
        {active === 'billing' ? <BillingTab /> : null}
      </div>
    </div>
  );
};
