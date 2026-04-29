import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';
import type { FC } from 'react';

export type LoadingStateProps = {
  /** Shown below the spinner */
  label?: string;
  className?: string;
};

export const LoadingState: FC<LoadingStateProps> = ({
  label = 'Loading…',
  className,
}) => (
  <div
    className={cn(
      'flex flex-col items-center justify-center gap-4 py-16',
      className,
    )}
    role="status"
    aria-live="polite"
    aria-busy="true"
  >
    <Loader2
      className="text-primary-400 size-9 animate-spin"
      strokeWidth={2}
      aria-hidden
    />
    {label ? (
      <p className="text-muted text-center text-sm font-medium">{label}</p>
    ) : null}
  </div>
);
