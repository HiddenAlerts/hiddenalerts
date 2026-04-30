import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

export type ComingSoonProps = {
  title: string;
  description?: string;
  className?: string;
  children?: ReactNode;
};

export const ComingSoon: FC<ComingSoonProps> = ({
  title,
  description,
  className,
  children,
}) => (
  <div
    className={cn('space-y-4', className)}
    role="status"
    aria-live="polite"
  >
    <div className="border-border bg-surface/40 rounded-lg border px-6 py-8 sm:px-8">
      <p className="text-muted mb-3 text-[0.65rem] font-semibold tracking-[0.18em] uppercase">
        Coming soon
      </p>
      <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight">
        {title}
      </h1>
      {description ? (
        <p className="text-muted mt-3 max-w-lg text-sm leading-relaxed">
          {description}
        </p>
      ) : null}
      {children ? <div className="mt-6">{children}</div> : null}
    </div>
  </div>
);
