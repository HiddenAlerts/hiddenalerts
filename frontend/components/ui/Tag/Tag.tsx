import { cn } from '@/lib/utils';
import type { FC } from 'react';

interface TagProps {
  title: string;
  size?: 'sm' | 'lg';
  dot?: boolean;
  shape?: 'square' | 'round';
  type?:
    | 'gray'
    | 'danger'
    | 'info'
    | 'warning'
    | 'success'
    | 'primary'
    | 'grayLight';
  textClassName?: string;
}

const tagBackgroundMap = {
  gray: 'bg-gray-100 border-gray-100',
  danger: 'bg-danger-100 border-danger-100',
  warning: 'bg-warning-100 border-warning-100',
  success: 'bg-success-100 border-success-100',
  info: 'bg-info-100 border-info-100',
  primary: 'bg-primary-100 border-primary-100',
  grayLight: 'bg-gray-50 border border-gray-200',
};

const tagDotMap = {
  gray: 'bg-gray-500',
  danger: 'bg-danger-500',
  warning: 'bg-warning-500',
  success: 'bg-success-500',
  info: 'bg-info-500',
  primary: 'bg-primary-500',
  grayLight: 'bg-gray-300',
};

const Tag: FC<TagProps> = ({
  title,
  size = 'sm',
  shape = 'round',
  type = 'success',
  dot = true,
  textClassName,
}) => {

  const sizeClass = size === 'sm' ? 'h-6 px-3' : 'h-9 px-4';
  const textSizeClass = size === 'sm' ? 'text-xs' : 'text-sm';
  const shapeClass = shape === 'round' ? 'rounded-full' : 'rounded';

  return (
    <div
      className={cn(
        'inline-flex w-max shrink-0 items-center justify-start gap-1.5 border',
        tagBackgroundMap[type],
        sizeClass,
        shapeClass,
      )}
    >
      {shape === 'round' && dot && (
        <div
          className={cn('size-2 shrink-0 rounded-full', tagDotMap[type])}
          aria-hidden
        />
      )}
      <span
        className={cn(
          'm-0 block font-medium leading-none text-black',
          textSizeClass,
          textClassName,
        )}
      >
        {title}
      </span>
    </div>
  );
};

export default Tag;
