import { cn } from '@/lib/utils';

import type { SourceVariant } from '@/data/landingSources';

type SourceIconProps = {
  variant: SourceVariant;
  className?: string;
};

function SealIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn('size-10 shrink-0', className)} aria-hidden>
      <circle cx="20" cy="20" r="19" fill="none" stroke="currentColor" strokeWidth="1" />
      <circle cx="20" cy="20" r="14" fill="none" stroke="currentColor" strokeWidth="0.75" opacity="0.6" />
      <path
        d="M20 8l1.8 4.5 4.8.4-3.6 3.1 1.1 4.7L20 18.8l-4.1 2.9 1.1-4.7-3.6-3.1 4.8-.4L20 8z"
        fill="currentColor"
        opacity="0.85"
      />
      <circle cx="20" cy="20" r="3" fill="none" stroke="currentColor" strokeWidth="0.75" />
    </svg>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn('size-10 shrink-0', className)} aria-hidden>
      <path
        d="M20 4L8 9v11c0 7.2 5.1 13.9 12 15 6.9-1.1 12-7.8 12-15V9L20 4z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
      />
      <path
        d="M20 12v8M16 16h8"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.7"
      />
    </svg>
  );
}

export function SourceIcon({ variant, className }: SourceIconProps) {
  if (variant === 'seal') return <SealIcon className={className} />;
  if (variant === 'shield') return <ShieldIcon className={className} />;
  return null;
}
