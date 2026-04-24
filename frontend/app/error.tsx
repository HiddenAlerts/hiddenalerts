'use client';

import { BrandedIssueScreen } from '@/components/errors/BrandedIssueScreen';
import { useEffect, type FC } from 'react';

type AppErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

const AppError: FC<AppErrorProps> = ({ error, reset }) => {
  useEffect(() => {
    console.error(error);
  }, [error]);

  const description =
    error.message?.trim() ||
    'Something unexpected happened. You can try again or return home.';

  const footer =
    process.env.NODE_ENV === 'development' && error.digest ? (
      <p className="text-muted-foreground mt-4 font-mono text-xs break-all">
        {error.digest}
      </p>
    ) : null;

  return (
    <BrandedIssueScreen
      code="Error"
      title="Something went wrong"
      description={description}
      onRetry={reset}
      footer={footer}
    />
  );
};

export default AppError;
