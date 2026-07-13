import { EmptyState } from '@/components/ui/EmptyState';
import { cn } from '@/lib/utils';
import type { SubscriberBrief } from '@/types/briefs';
import type { FC } from 'react';

import { BriefCard } from './BriefCard';

export type BriefsGridProps = {
  briefs: SubscriberBrief[];
  className?: string;
};

/** Library grid — 3 columns on desktop (mockup); compact 16:9 thumbs. */
export const BriefsGrid: FC<BriefsGridProps> = ({ briefs, className }) => {
  if (briefs.length === 0) {
    return (
      <EmptyState
        title="No briefs found"
        description="No intelligence briefs match your current search and filters. Try adjusting them or resetting."
      />
    );
  }

  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3',
        className,
      )}
    >
      {briefs.map(brief => (
        <BriefCard
          key={brief.id}
          brief={brief}
          imageClassName="aspect-[16/9]"
        />
      ))}
    </div>
  );
};
