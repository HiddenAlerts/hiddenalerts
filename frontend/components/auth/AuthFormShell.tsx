import { LandingLogo } from '@/components/landing/LandingLogo';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import type { ReactNode } from 'react';

type AuthFormShellProps = {
  title: string;
  subtitle?: string;
  footer: {
    prompt: string;
    linkLabel: string;
    href: string;
  };
  children: ReactNode;
  className?: string;
};

export function AuthFormShell({
  title,
  subtitle,
  footer,
  children,
  className,
}: AuthFormShellProps) {
  return (
    <main className="text-foreground bg-background relative flex flex-1 flex-col items-center justify-center px-4 py-12 sm:py-16">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
      >
        <div className="bg-primary-500/20 absolute -top-32 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full blur-3xl" />
        <div className="bg-info-500/10 absolute right-1/3 bottom-0 h-64 w-64 rounded-full blur-3xl" />
      </div>

      <div
        className={cn(
          'border-border bg-surface/70 w-full max-w-md rounded-lg border p-6 shadow-md backdrop-blur sm:p-8',
          className,
        )}
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
            {title}
          </h1>
          {subtitle ? (
            <p className="text-muted text-sm leading-relaxed sm:text-base">
              {subtitle}
            </p>
          ) : null}
        </div>

        <div className="mt-7">{children}</div>

        <p className="text-muted mt-7 text-center text-sm">
          {footer.prompt}{' '}
          <Link
            href={footer.href}
            className="text-primary-500 hover:text-primary-400 focus-visible:ring-primary-500 rounded-sm font-medium underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:outline-none"
          >
            {footer.linkLabel}
          </Link>
        </p>
      </div>
    </main>
  );
}
