import { BRIEF_CATEGORY_FILTER_ALL } from '@/data/subscriberBriefs';
import { cn } from '@/lib/utils';
import type { BriefCountItem } from '@/types/briefs';
import { Layers } from 'lucide-react';
import type { FC } from 'react';

import { SidebarPanel } from './SidebarPanel';

export type BriefCategoriesPanelProps = {
  categories: BriefCountItem[];
  total: number;
  activeCategory: string;
  onSelectCategory: (category: string) => void;
  className?: string;
};

type RowProps = {
  label: string;
  count: number;
  active: boolean;
  onSelect: () => void;
};

const CategoryRow: FC<RowProps> = ({ label, count, active, onSelect }) => (
  <li>
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      className={cn(
        'flex w-full cursor-pointer items-center justify-between gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors',
        active
          ? 'bg-primary-500/15 text-foreground font-semibold'
          : 'text-body hover:bg-surface hover:text-foreground',
      )}
    >
      <span className="truncate">{label}</span>
      <span
        className={cn(
          'shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums',
          active ? 'bg-primary-500 text-white' : 'bg-surface text-muted',
        )}
      >
        {count}
      </span>
    </button>
  </li>
);

export const BriefCategoriesPanel: FC<BriefCategoriesPanelProps> = ({
  categories,
  total,
  activeCategory,
  onSelectCategory,
  className,
}) => (
  <SidebarPanel
    title="Categories"
    icon={<Layers className="text-danger" aria-hidden />}
    className={className}
  >
    <ul className="space-y-0.5" role="list">
      <CategoryRow
        label="All Briefs"
        count={total}
        active={activeCategory === BRIEF_CATEGORY_FILTER_ALL}
        onSelect={() => onSelectCategory(BRIEF_CATEGORY_FILTER_ALL)}
      />
      {categories.map(category => (
        <CategoryRow
          key={category.label}
          label={category.label}
          count={category.count}
          active={activeCategory === category.label}
          onSelect={() => onSelectCategory(category.label)}
        />
      ))}
    </ul>
  </SidebarPanel>
);
