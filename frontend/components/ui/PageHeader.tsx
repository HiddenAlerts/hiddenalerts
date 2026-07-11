import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

export type PageHeaderProps = {
  title: string;
  subtitle?: string;
  /** Optional leading icon rendered in a rounded square before the title. */
  icon?: ReactNode;
  /** Rendered on the right side (e.g. primary CTA buttons). */
  actions?: ReactNode;
  className?: string;
};

/**
 * Reusable page header with a title, optional subtitle, and a right-aligned
 * action slot. Used across admin and user pages.
 */
export const PageHeader: FC<PageHeaderProps> = ({
  title,
  subtitle,
  icon,
  actions,
  className,
}) => (
  <div
    className={cn(
      'flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6',
      className,
    )}
  >
    <div className="flex min-w-0 items-start gap-3">
      {icon ? (
        <span className="bg-primary-500 text-foreground flex size-10 shrink-0 items-center justify-center rounded-lg">
          {icon}
        </span>
      ) : null}
      <div className="min-w-0 space-y-1">
        <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight sm:text-[1.7rem]">
          {title}
        </h1>
        {subtitle ? (
          <p className="text-muted text-sm sm:text-[0.95rem]">{subtitle}</p>
        ) : null}
      </div>
    </div>
    {actions ? (
      <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
        {actions}
      </div>
    ) : null}
  </div>
);
