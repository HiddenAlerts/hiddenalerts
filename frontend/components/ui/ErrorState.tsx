import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { FC } from 'react';

export type ErrorStateProps = {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
};

export const ErrorState: FC<ErrorStateProps> = ({
  title = 'Something went wrong',
  message,
  onRetry,
  className,
}) => (
  <div
    className={cn(
      'border-border bg-background-alt text-center',
      'rounded-lg border px-6 py-12',
      className,
    )}
    role="alert"
  >
    <p className="text-foreground font-medium">{title}</p>
    <p className="text-muted mx-auto mt-2 max-w-md text-sm leading-relaxed">
      {message}
    </p>
    {onRetry ? (
      <div className="mt-6 flex justify-center">
        <Button type="button" variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      </div>
    ) : null}
  </div>
);
