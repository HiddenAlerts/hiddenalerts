import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

export type LandingSectionProps = {
  id?: string;
  /** Applied to the outer <section> (background, borders, vertical padding). */
  className?: string;
  /** Applied to the centered inner container (controls max width / layout). */
  containerClassName?: string;
  /** Accessible label association for the section heading. */
  ariaLabelledby?: string;
  children: ReactNode;
};

/**
 * Shared marketing section shell: consistent horizontal padding, scroll offset
 * for anchor links, and a centered max-width container. Keeps every landing
 * section visually aligned without repeating layout classes.
 */
export function LandingSection({
  id,
  className,
  containerClassName,
  ariaLabelledby,
  children,
}: LandingSectionProps) {
  return (
    <section
      id={id}
      aria-labelledby={ariaLabelledby}
      className={cn('scroll-mt-20 px-4 py-10 md:px-6 md:py-12', className)}
    >
      <div className={cn('mx-auto w-full max-w-6xl', containerClassName)}>
        {children}
      </div>
    </section>
  );
}

export type SectionHeadingProps = {
  id?: string;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  align?: 'center' | 'left';
  className?: string;
};

/** Reusable section heading block (optional eyebrow + title + subtitle). */
export function SectionHeading({
  id,
  eyebrow,
  title,
  subtitle,
  align = 'center',
  className,
}: SectionHeadingProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3',
        align === 'center' ? 'items-center text-center' : 'items-start text-left',
        className,
      )}
    >
      {eyebrow ? (
        <span className="text-primary-400 text-xs font-semibold tracking-[0.18em] uppercase">
          {eyebrow}
        </span>
      ) : null}
      <h2
        id={id}
        className="font-heading text-foreground text-2xl font-semibold tracking-tight text-balance sm:text-3xl"
      >
        {title}
      </h2>
      {subtitle ? (
        <p className="text-muted max-w-2xl text-sm leading-relaxed sm:text-base">
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}
