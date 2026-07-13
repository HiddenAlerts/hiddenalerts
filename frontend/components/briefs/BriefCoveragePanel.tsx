import { COVERAGE_AREAS } from '@/data/coverageAreas';
import { cn } from '@/lib/utils';
import { Globe } from 'lucide-react';
import type { FC } from 'react';

import { SidebarPanel } from './SidebarPanel';

export type BriefCoveragePanelProps = {
  className?: string;
};

/** Ken’s fixed coverage list (display-only — not tag-count driven). */
export const BriefCoveragePanel: FC<BriefCoveragePanelProps> = ({
  className,
}) => (
  <SidebarPanel
    title="Intelligence Brief Coverage"
    icon={<Globe className="text-danger" aria-hidden />}
    className={className}
  >
    <ul className="space-y-2.5" role="list">
      {COVERAGE_AREAS.map(item => {
        const Icon = item.icon;
        return (
          <li
            key={item.id}
            className="text-body flex items-center gap-2.5 text-sm"
          >
            <Icon
              className="text-danger size-4 shrink-0"
              strokeWidth={1.75}
              aria-hidden
            />
            <span className={cn('min-w-0 leading-snug')}>{item.label}</span>
          </li>
        );
      })}
    </ul>
  </SidebarPanel>
);
