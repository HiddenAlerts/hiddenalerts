import { cn } from '@/lib/utils';
import React from 'react';

import type { TypographyProps } from './Typography.types';
import { getFontWeight, variantMapping, variantStyles } from './typographyData';

const Typography = React.forwardRef<HTMLElement, TypographyProps>(
  ({ as, children, className = '', fontWeight, variant, ...props }, ref) => {
    const Component = (as || variantMapping[variant]) as React.ElementType;

    const classes = cn(
      getFontWeight(variant, fontWeight),
      variantStyles[variant],
      className,
    );

    return (
      <Component ref={ref} className={classes} {...props}>
        {children}
      </Component>
    );
  },
);

Typography.displayName = 'Typography';

export default Typography;
