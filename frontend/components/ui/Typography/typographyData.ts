import { type JSX } from 'react';

import type { FontWeight, Variant } from './Typography.types';

export const variantStyles: Record<Variant, string> = {
  h1: 'text-6xl leading-[1.2] !font-figtree', // 60px
  h2: 'text-[56px] leading-[1.2] !font-figtree', // 56px
  h3: 'text-5xl leading-[1.2] !font-figtree', // 48px
  h4: 'text-[40px] leading-[1.2] !font-figtree', // 40px
  h5: 'text-[32px] leading-[1.22] !font-figtree', // 32px
  h6: 'text-2xl leading-[1.21] !font-figtree', // 24px
  body1: 'text-lg leading-[1.223]', // 18px
  body2: 'text-base leading-sm', // 16px
  body3: 'text-sm leading-sm', // 14px
  caption: 'text-xs leading-sm', // 12px
  footer: 'text-[10px] leading-sm', // 10px
};

const headingTags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'];

export const variantMapping: Record<Variant, keyof JSX.IntrinsicElements> = {
  h1: 'h1',
  h2: 'h2',
  h3: 'h3',
  h4: 'h4',
  h5: 'h5',
  h6: 'h6',
  body1: 'p',
  body2: 'p',
  body3: 'p',
  caption: 'span',
  footer: 'p',
};

export const getFontWeight = (variant: Variant, fontWeight?: FontWeight) => {
  const isHeading = headingTags.includes(variant);

  if (isHeading) {
    switch (fontWeight) {
      case 'extrabold':
        return 'font-extrabold';
      case 'semibold':
        return 'font-semibold';
      default:
        return 'font-bold';
    }
  } else {
    switch (fontWeight) {
      case 'medium':
        return 'font-medium';
      case 'semibold':
        return 'font-semibold';
      default:
        return 'font-normal';
    }
  }
};
