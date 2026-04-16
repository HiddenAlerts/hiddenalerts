import { cn } from '@/lib/utils';
import { type VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import * as React from 'react';

import { buttonSpinnerSize, buttonVariants } from './button.styles';

export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      loading = false,
      leftIcon,
      rightIcon,
      children,
      disabled,
      onClick,
      type = 'button',
      ...props
    },
    ref,
  ) => {
    const spinnerClass =
      variant === 'outline' || variant === 'link' || variant === 'secondary'
        ? 'text-primary-600'
        : variant === 'danger-link'
          ? 'text-danger'
          : variant === 'danger'
            ? 'text-current'
            : 'text-white';

    return (
      <button
        ref={ref}
        type={type}
        className={cn(
          buttonVariants({ variant, size }),
          loading && 'pointer-events-none opacity-40',
          className,
        )}
        disabled={disabled || loading}
        onClick={disabled || loading ? undefined : onClick}
        {...props}
      >
        {leftIcon}
        {children}
        {loading && (
          <Loader2
            aria-hidden
            className={cn(
              'shrink-0 animate-spin',
              buttonSpinnerSize[size ?? 'md'],
              spinnerClass,
            )}
          />
        )}
        {!loading && rightIcon}
      </button>
    );
  },
);

Button.displayName = 'Button';

export { Button, buttonVariants };
