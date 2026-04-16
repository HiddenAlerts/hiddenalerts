'use client';

import { cn } from '@/lib/utils';
import { type VariantProps } from 'class-variance-authority';
import { Eye, EyeOff } from 'lucide-react';
import * as React from 'react';

import { inputVariants, labelSize } from './input.styles';

function renderIcon(
  icon: React.ReactNode | string | undefined,
  iconClassName: string,
  side: 'left' | 'right',
) {
  if (!icon) {
    return null;
  }

  if (typeof icon === 'string') {
    return (
      // External or data URLs from callers; Next/Image is optional at call sites.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={icon}
        alt=""
        className={cn(iconClassName, 'shrink-0 object-contain')}
        aria-hidden
      />
    );
  }

  return (
    <span
      className={cn(
        'text-muted flex shrink-0 items-center justify-center [&_svg]:size-4',
        side === 'left' ? 'mr-2' : 'ml-2',
      )}
      aria-hidden
    >
      {icon}
    </span>
  );
}

export interface InputProps
  extends
    Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'>,
    VariantProps<typeof inputVariants> {
  label?: string;
  labelStyles?: string;
  parentStyles?: string;
  isError?: boolean;
  errorMessage?: string;
  addAsterisk?: boolean;
  passwordWithIcon?: boolean;
  /** Image URL or a React node (e.g. Lucide icon). */
  leftIcon?: React.ReactNode | string;
  rightIcon?: React.ReactNode | string;
  leftIconStyles?: string;
  rightIconStyles?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      name,
      id,
      type = 'text',
      variant,
      inputSize,
      label,
      labelStyles,
      parentStyles,
      isError,
      errorMessage,
      addAsterisk,
      required,
      disabled,
      passwordWithIcon,
      leftIcon,
      rightIcon,
      leftIconStyles = 'h-5 w-5',
      rightIconStyles = 'h-5 w-5',
      ...props
    },
    ref,
  ) => {
    const uid = React.useId();
    const size = inputSize ?? 'md';
    const fieldId = id ?? (name !== undefined ? String(name) : `input-${uid}`);
    const showAsterisk = Boolean(
      required && addAsterisk && label && !label.includes('*'),
    );
    const showPasswordToggle = Boolean(passwordWithIcon && type === 'password');

    const [passwordVisible, setPasswordVisible] = React.useState(false);
    const innerRef = React.useRef<HTMLInputElement>(null);

    React.useImperativeHandle(ref, () => innerRef.current as HTMLInputElement);

    const resolvedVariant = isError ? 'error' : (variant ?? 'default');
    const inputType = showPasswordToggle && passwordVisible ? 'text' : type;

    const handleShellClick = () => {
      innerRef.current?.focus();
    };

    const handleTogglePassword = (e: React.MouseEvent) => {
      e.stopPropagation();
      setPasswordVisible(v => !v);
    };

    return (
      <div
        className={cn(
          'relative flex flex-col gap-2',
          disabled && 'cursor-not-allowed',
          parentStyles,
        )}
      >
        {label ? (
          <label htmlFor={fieldId} className={cn(labelSize[size], labelStyles)}>
            {label}
            {showAsterisk ? (
              <span className="text-danger-500 ml-0.5 font-medium">*</span>
            ) : null}
          </label>
        ) : null}

        <div
          role="presentation"
          onClick={handleShellClick}
          className={cn(
            inputVariants({ variant: resolvedVariant, inputSize: size }),
            disabled && 'pointer-events-none opacity-40',
            className,
          )}
        >
          {renderIcon(leftIcon, leftIconStyles, 'left')}

          <input
            ref={innerRef}
            id={fieldId}
            name={name}
            type={inputType}
            disabled={disabled}
            required={required}
            className={cn(
              'text-body placeholder:text-muted min-w-0 flex-1 bg-transparent focus-visible:outline-none disabled:cursor-not-allowed',
            )}
            {...props}
          />

          {showPasswordToggle ? (
            <button
              type="button"
              tabIndex={-1}
              disabled={disabled}
              onClick={handleTogglePassword}
              className="text-muted hover:text-foreground ml-2 shrink-0 disabled:opacity-40"
              aria-label={passwordVisible ? 'Hide password' : 'Show password'}
            >
              {passwordVisible ? (
                <EyeOff className="size-5" aria-hidden />
              ) : (
                <Eye className="size-5" aria-hidden />
              )}
            </button>
          ) : null}

          {!showPasswordToggle
            ? renderIcon(rightIcon, rightIconStyles, 'right')
            : null}
        </div>

        {isError && errorMessage ? (
          <p className="text-danger-400 text-xs">{errorMessage}</p>
        ) : null}
      </div>
    );
  },
);

Input.displayName = 'Input';

export { Input, inputVariants, labelSize };
