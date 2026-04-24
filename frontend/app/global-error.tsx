'use client';

import { BrandedIssueScreen } from '@/components/errors/BrandedIssueScreen';
import { Figtree, Manrope } from 'next/font/google';
import { useEffect, type FC } from 'react';

import './globals.css';

const manrope = Manrope({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-manrope',
});

const figtree = Figtree({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-figtree',
});

type GlobalErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

const GlobalError: FC<GlobalErrorProps> = ({ error, reset }) => {
  useEffect(() => {
    console.error(error);
  }, [error]);

  const description =
    process.env.NODE_ENV === 'development' && error.message?.trim()
      ? error.message
      : 'We could not load the application. Please try again.';

  return (
    <html
      lang="en"
      className={`${manrope.variable} ${figtree.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body
        className={`${manrope.className} bg-background text-foreground flex min-h-full flex-col`}
      >
        <BrandedIssueScreen
          code="Error"
          title="Something went wrong"
          description={description}
          onRetry={reset}
          footer={
            process.env.NODE_ENV === 'development' && error.digest ? (
              <p className="text-muted-foreground mt-4 font-mono text-xs break-all">
                {error.digest}
              </p>
            ) : null
          }
        />
      </body>
    </html>
  );
};

export default GlobalError;
