import { Button } from '@/components';
import { cn } from '@/lib/utils';
import { ChevronRight, ShieldCheck, Sparkles } from 'lucide-react';
import Link from 'next/link';
import type { FC } from 'react';

export type DashboardUnlockCtaProps = {
  title: string;
  description: string;
  primaryLabel: string;
  secondaryLabel: string;
  onPrimaryClick?: () => void;
  secondaryHref?: string;
  className?: string;
};

export const DashboardUnlockCta: FC<DashboardUnlockCtaProps> = ({
  title,
  description,
  primaryLabel,
  secondaryLabel,
  onPrimaryClick,
  secondaryHref = '/',
  className,
}) => (
  <div
    className={cn(
      'border-danger/45 bg-danger-500/5 relative z-0 overflow-hidden rounded-md border p-4 shadow-sm sm:p-5 lg:p-4',
      className,
    )}
  >
    <div className="relative z-10 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between sm:gap-6 lg:gap-8">
      <div className="flex min-w-0 flex-1 gap-4 sm:gap-5">
        <div className="relative flex size-12 shrink-0 items-center justify-center sm:size-14">
          <ShieldCheck
            className="text-danger size-9 sm:size-10"
            strokeWidth={1.75}
            aria-hidden
          />
          <Sparkles
            className="text-danger absolute -top-0.5 -right-0.5 size-4 sm:size-[1.125rem]"
            strokeWidth={1.75}
            aria-hidden
          />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <h2 className="font-heading text-foreground text-base font-semibold tracking-tight sm:text-lg">
            {title}
          </h2>
          <p className="text-muted max-w-3xl text-sm leading-relaxed">
            {description}
          </p>
        </div>
      </div>

      <div className="flex shrink-0 flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
        <Button type="button" size="sm" onClick={onPrimaryClick}>
          {primaryLabel}
        </Button>
        {/* <Link
          href={secondaryHref}
          className="text-foreground hover:text-body inline-flex cursor-pointer items-center gap-0.5 text-sm font-semibold transition-colors"
        >
          {secondaryLabel}
          <ChevronRight className="size-4 shrink-0" aria-hidden />
        </Link> */}
      </div>
    </div>
  </div>
);
