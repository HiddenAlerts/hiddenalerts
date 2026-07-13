import { cn } from '@/lib/utils';
import type { BriefCountItem } from '@/types/briefs';
import type { FC } from 'react';

import { BriefCategoriesPanel } from './BriefCategoriesPanel';
import { BriefCoveragePanel } from './BriefCoveragePanel';
import { WhySubscribersPanel } from './WhySubscribersPanel';

export type BriefsLibrarySidebarProps = {
  categories: BriefCountItem[];
  total: number;
  activeCategory: string;
  onSelectCategory: (category: string) => void;
  className?: string;
};

export const BriefsLibrarySidebar: FC<BriefsLibrarySidebarProps> = ({
  categories,
  total,
  activeCategory,
  onSelectCategory,
  className,
}) => (
  <aside className={cn('space-y-4', className)} aria-label="Brief library details">
    <WhySubscribersPanel />
    <BriefCategoriesPanel
      categories={categories}
      total={total}
      activeCategory={activeCategory}
      onSelectCategory={onSelectCategory}
    />
    <BriefCoveragePanel />
  </aside>
);
