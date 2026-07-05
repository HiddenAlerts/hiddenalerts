import { cn } from '@/lib/utils';
import type { BriefCoverTheme } from '@/types/briefs';
import {
  AlertTriangle,
  Coins,
  Globe,
  Landmark,
  type LucideIcon,
  Shield,
  ShieldAlert,
  UserRound,
  Users,
} from 'lucide-react';
import type { FC, ReactNode } from 'react';

const coverGradient: Record<BriefCoverTheme, string> = {
  'emerging-threat':
    'bg-[radial-gradient(circle_at_30%_25%,rgba(238,68,66,0.28),transparent_60%),linear-gradient(135deg,#1a0f1e,#160d14_55%,#0c0a12)]',
  'financial-crime':
    'bg-[radial-gradient(circle_at_70%_30%,rgba(255,178,71,0.20),transparent_55%),linear-gradient(135deg,#0d1f37,#0a1422_55%,#0c1424)]',
  cyber:
    'bg-[radial-gradient(circle_at_30%_30%,rgba(79,140,255,0.24),transparent_60%),linear-gradient(135deg,#0b1c3a,#0a1426_55%,#101a2e)]',
  'national-security':
    'bg-[radial-gradient(circle_at_60%_35%,rgba(79,140,255,0.22),transparent_60%),linear-gradient(135deg,#142339,#0e1a2c_60%,#0a1422)]',
  fraud:
    'bg-[radial-gradient(circle_at_25%_30%,rgba(238,68,66,0.22),transparent_55%),linear-gradient(135deg,#1c1018,#140c12_55%,#0c0a10)]',
  identity:
    'bg-[radial-gradient(circle_at_70%_40%,rgba(99,180,255,0.22),transparent_55%),linear-gradient(135deg,#0c1c34,#0a1426_55%,#080f1d)]',
  corruption:
    'bg-[radial-gradient(circle_at_40%_30%,rgba(255,178,71,0.18),transparent_55%),linear-gradient(135deg,#1a1626,#12101c_55%,#0b0a12)]',
  'organized-crime':
    'bg-[radial-gradient(circle_at_30%_30%,rgba(238,68,66,0.20),transparent_55%),linear-gradient(135deg,#161018,#100c12_55%,#0a0810)]',
};

const coverIcon: Record<BriefCoverTheme, LucideIcon> = {
  'emerging-threat': AlertTriangle,
  'financial-crime': Coins,
  cyber: Globe,
  'national-security': Shield,
  fraud: ShieldAlert,
  identity: UserRound,
  corruption: Landmark,
  'organized-crime': Users,
};

export type BriefCoverProps = {
  theme: BriefCoverTheme;
  className?: string;
  /** Tailwind size class for the decorative icon, e.g. `size-32`. */
  iconSizeClassName?: string;
  /** Overlaid content (risk score, badges, etc.). */
  children?: ReactNode;
};

/** Decorative gradient + themed icon background shared by every brief card. */
export const BriefCover: FC<BriefCoverProps> = ({
  theme,
  className,
  iconSizeClassName = 'size-28',
  children,
}) => {
  const Icon = coverIcon[theme];
  return (
    <div
      className={cn('relative overflow-hidden', coverGradient[theme], className)}
    >
      <div className="absolute inset-0 flex items-center justify-center text-white">
        <Icon
          className={cn(iconSizeClassName, 'opacity-15')}
          strokeWidth={1}
          aria-hidden
        />
      </div>
      {children}
    </div>
  );
};
