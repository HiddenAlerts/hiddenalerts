import { buttonVariants } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

type LandingEmailFormProps = {
  actionUrl: string;
  placeholder?: string;
  buttonLabel: string;
  /** 'red' for primary CTAs, 'blue' for free tier */
  variant?: 'red' | 'blue';
  className?: string;
  inputClassName?: string;
  buttonClassName?: string;
  buttonIcon?: ReactNode;
};

export function LandingEmailForm({
  actionUrl,
  placeholder = 'Enter your email',
  buttonLabel,
  variant = 'red',
  className,
  inputClassName,
  buttonClassName,
  buttonIcon,
}: LandingEmailFormProps) {
  const buttonColor =
    variant === 'blue'
      ? 'bg-info hover:bg-info/90 text-white'
      : undefined;

  return (
    <form
      action={actionUrl}
      method="get"
      target="_blank"
      rel="noopener noreferrer"
      className={cn('flex flex-col gap-2 sm:flex-row sm:items-stretch', className)}
    >
      <Input
        name="email"
        type="email"
        inputSize="md"
        placeholder={placeholder}
        autoComplete="email"
        required
        aria-label="Email address"
        parentStyles={cn('w-full min-w-0 sm:flex-1', inputClassName)}
        className="border-border bg-surface/60 h-11"
      />
      <button
        type="submit"
        className={cn(
          buttonVariants({ variant: 'default', size: 'md' }),
          'h-11 shrink-0 gap-2 px-5 text-sm font-semibold whitespace-nowrap',
          buttonColor,
          buttonClassName,
        )}
      >
        {buttonIcon}
        {buttonLabel}
      </button>
    </form>
  );
}
