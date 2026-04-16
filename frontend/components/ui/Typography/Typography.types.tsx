import { type JSX } from 'react';

export type Variant =
  | 'h1'
  | 'h2'
  | 'h3'
  | 'h4'
  | 'h5'
  | 'h6'
  | 'body1'
  | 'body2'
  | 'body3'
  | 'caption'
  | 'footer';

export type FontWeight =
  | 'regular'
  | 'medium'
  | 'bold'
  | 'semibold'
  | 'extrabold';

export interface TypographyProps extends React.HTMLAttributes<HTMLElement> {
  as?: keyof JSX.IntrinsicElements;
  children: React.ReactNode;
  fontWeight?: FontWeight;
  styles?: string;
  variant: Variant;
}
