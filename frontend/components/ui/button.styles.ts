import { cva } from 'class-variance-authority';

export const buttonVariants = cva(
  'font-manrope inline-flex cursor-pointer items-center justify-center gap-2 font-medium whitespace-nowrap transition-all duration-300 ease-in-out disabled:pointer-events-none disabled:opacity-40',
  {
    variants: {
      variant: {
        default:
          'border-primary-500 bg-primary-500 hover:border-primary-600 hover:bg-primary-600 active:border-primary-700 active:bg-primary-700 border text-white',
        outline:
          'border-border bg-article-bg text-article-foreground hover:border-border border hover:bg-gray-50 active:bg-gray-100',
        link: 'text-primary-500 hover:text-primary-600 active:text-primary-700 border-transparent bg-transparent',
        secondary:
          'border border-gray-200 bg-gray-100 text-gray-900 hover:border-gray-300 hover:bg-gray-200 active:border-gray-400 active:bg-gray-300',
        danger:
          'border-danger-200 bg-danger-50 text-danger-600 hover:border-danger-300 hover:bg-danger-100 active:border-danger-400 active:bg-danger-200 border',
        'danger-link':
          '!text-danger hover:!text-danger-600 active:!text-danger-700 border-transparent bg-transparent',
      },
      size: {
        lg: 'rounded-md px-8 py-4 text-lg',
        md: 'rounded-md px-8 py-3 text-base',
        sm: 'rounded-sm px-6 py-2 text-sm',
        xs: 'h-[30px] rounded-sm px-6 py-2 text-xs font-semibold',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  },
);

export const buttonSpinnerSize = {
  lg: 'size-[18px]',
  md: 'size-4',
  sm: 'size-[14px]',
  xs: 'size-3',
} as const;
