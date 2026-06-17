import { cva } from 'class-variance-authority';

export const labelSize = {
  lg: 'text-base font-medium leading-5',
  md: 'text-sm font-medium leading-5',
  sm: 'text-sm font-medium leading-5',
  xs: 'text-xs font-medium leading-[14px]',
} as const;

export const inputVariants = cva(
  'font-manrope bg-surface text-body flex w-full min-w-0 items-center border transition-colors',
  {
    variants: {
      variant: {
        default:
          'border-border focus-within:border-primary-500 focus-within:ring-primary-500/30 focus-within:ring-2',
        error:
          'border-danger focus-within:border-danger focus-within:ring-danger/25 focus-within:ring-2',
      },
      inputSize: {
        xs: 'h-[30px] rounded-sm px-2 text-xs',
        sm: 'h-9 rounded-sm px-2.5 text-sm',
        md: 'h-11 rounded-md px-3 text-base',
        lg: 'h-[52px] rounded-md px-3.5 text-lg',
      },
    },
    defaultVariants: {
      variant: 'default',
      inputSize: 'md',
    },
  },
);
