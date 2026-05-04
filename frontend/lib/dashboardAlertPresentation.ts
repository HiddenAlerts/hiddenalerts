import type { LucideIcon } from 'lucide-react';
import {
  Bell,
  Coins,
  Globe,
  type LucideProps,
  Shield,
  UserRound,
} from 'lucide-react';
import { createElement, type FC } from 'react';

export function formatDashboardAlertTypeLabel(category: string) {
  if (!category) return 'General';
  return category.replace(/\b\w/g, ch => ch.toUpperCase());
}

const categoryIconMap: Record<string, LucideIcon> = {
  security: UserRound,
  network: Globe,
  system: Shield,
  finance: Coins,
  crypto: Coins,
};

export function getDashboardAlertCategoryIcon(
  category: string,
): LucideIcon {
  const key = category.trim().toLowerCase();
  return categoryIconMap[key] ?? Bell;
}

export type DashboardCategoryIconProps = LucideProps & {
  category: string;
};

export const DashboardCategoryIcon: FC<DashboardCategoryIconProps> = ({
  category,
  className,
  ...rest
}) => {
  const Icon = getDashboardAlertCategoryIcon(category);
  return createElement(Icon, {
    className,
    'aria-hidden': true,
    ...rest,
  });
};
