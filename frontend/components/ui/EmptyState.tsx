import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

export type EmptyStateProps = {
  title: string;
  description?: string;
  className?: string;
  children?: ReactNode;
};

export const EmptyState: FC<EmptyStateProps> = ({
  title,
  description,
  className,
  children,
}) => (
  <div
    className={cn(
      'border-border bg-background-alt text-center',
      'rounded-lg border px-6 py-12',
      className,
    )}
    role="status"
  >
    <p className="text-foreground font-medium">{title}</p>
    {description ? (
      <p className="text-muted mx-auto mt-2 max-w-md text-sm leading-relaxed">
        {description}
      </p>
    ) : null}
    {children ? <div className="mt-6 flex justify-center">{children}</div> : null}
  </div>
);
