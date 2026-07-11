import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';
import {
  BarChart3,
  Building2,
  Hexagon,
  Laptop,
  ScanSearch,
  Star,
  Target,
  Users,
} from 'lucide-react';

import { LandingSection } from './LandingSection';

type BuiltForItem = {
  icon: LucideIcon;
  label: string;
  iconClassName?: string;
};

const BUILT_FOR_ITEMS: ReadonlyArray<BuiltForItem> = [
  { icon: ScanSearch, label: 'Fraud Investigators' },
  { icon: Users, label: 'BSA/AML Professionals' },
  { icon: Laptop, label: 'Compliance Officers' },
  { icon: Target, label: 'Risk Managers' },
  { icon: Building2, label: 'Banks' },
  { icon: BarChart3, label: 'Fintech Companies' },
  {
    icon: Star,
    label: 'Payment Providers',
    iconClassName: 'relative',
  },
];

function PaymentProviderIcon({ className }: { className?: string }) {
  return (
    <span className={cn('relative inline-flex size-9 items-center justify-center', className)}>
      <Hexagon
        className="text-muted-foreground/70 absolute size-9"
        strokeWidth={1.25}
        aria-hidden
      />
      <Star
        className="text-muted-foreground relative size-4"
        strokeWidth={1.5}
        aria-hidden
      />
    </span>
  );
}

function BuiltForItemCell({ item, showDivider }: { item: BuiltForItem; showDivider: boolean }) {
  const Icon = item.icon;
  const isPayment = item.label === 'Payment Providers';

  return (
    <li
      className={cn(
        'flex flex-1 flex-col items-center gap-3 px-3 py-2 text-center sm:px-4',
        showDivider && 'border-border/60 lg:border-r lg:last:border-r-0',
      )}
    >
      {isPayment ? (
        <PaymentProviderIcon />
      ) : (
        <Icon
          className="text-muted-foreground size-8 sm:size-9"
          strokeWidth={1.25}
          aria-hidden
        />
      )}
      <span className="text-muted-foreground text-[0.65rem] leading-snug font-medium sm:text-xs">
        {item.label}
      </span>
    </li>
  );
}

export function LandingBuiltFor() {
  return (
    <LandingSection className="border-border-subtle border-t py-14 md:py-20">
      <div className="border-border/80 mx-auto max-w-5xl rounded-2xl border px-4 py-8 sm:px-6 sm:py-10 md:px-8 md:py-12">
        <h2 className="text-muted-foreground text-center text-xs font-semibold tracking-[0.2em] uppercase sm:text-sm">
          Built For
        </h2>

        <ul className="mt-8 grid grid-cols-2 gap-6 sm:grid-cols-3 md:grid-cols-4 lg:mt-10 lg:flex lg:gap-0">
          {BUILT_FOR_ITEMS.map((item, index) => (
            <BuiltForItemCell
              key={item.label}
              item={item}
              showDivider={index < BUILT_FOR_ITEMS.length - 1}
            />
          ))}
        </ul>
      </div>
    </LandingSection>
  );
}
