import { cn } from '@/lib/utils';
import type { BriefCountItem } from '@/types/briefs';
import { Globe } from 'lucide-react';
import type { FC } from 'react';

import { SidebarPanel } from './SidebarPanel';

export type BriefCoveragePanelProps = {
  coverage: BriefCountItem[];
  className?: string;
};

export const BriefCoveragePanel: FC<BriefCoveragePanelProps> = ({
  coverage,
  className,
}) => (
  <SidebarPanel
    title="Intelligence Brief Coverage"
    icon={<Globe className="text-danger" aria-hidden />}
    className={className}
  >
    <ul className="space-y-2.5" role="list">
      {coverage.map(item => (
        <li
          key={item.label}
          className="flex items-center justify-between gap-2 text-sm"
        >
          <span className="text-body inline-flex min-w-0 items-center gap-2">
            <span
              className="bg-danger size-1.5 shrink-0 rounded-full"
              aria-hidden
            />
            <span className="truncate">{item.label}</span>
          </span>
          <span
            className={cn(
              'text-muted shrink-0 text-xs font-semibold tabular-nums',
            )}
          >
            {item.count}
          </span>
        </li>
      ))}
    </ul>
  </SidebarPanel>
);
