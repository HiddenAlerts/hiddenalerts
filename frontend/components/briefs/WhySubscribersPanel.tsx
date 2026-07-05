import { WHY_SUBSCRIBERS_REASONS } from '@/data/subscriberBriefs';
import { CheckCircle2, ShieldCheck } from 'lucide-react';
import type { FC } from 'react';

import { SidebarPanel } from './SidebarPanel';

export const WhySubscribersPanel: FC<{ className?: string }> = ({
  className,
}) => (
  <SidebarPanel
    title="Why Subscribers Use HiddenAlerts"
    icon={<ShieldCheck className="text-danger" aria-hidden />}
    className={className}
  >
    <ul className="space-y-3" role="list">
      {WHY_SUBSCRIBERS_REASONS.map(reason => (
        <li key={reason.title} className="flex gap-2.5">
          <CheckCircle2
            className="text-danger mt-0.5 size-4 shrink-0"
            aria-hidden
          />
          <div className="min-w-0">
            <p className="text-foreground text-sm font-semibold leading-snug">
              {reason.title}
            </p>
            <p className="text-muted text-xs leading-relaxed">
              {reason.description}
            </p>
          </div>
        </li>
      ))}
    </ul>
  </SidebarPanel>
);
