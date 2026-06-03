'use client';

import { Input } from '@/components';
import { cn } from '@/lib/utils';
import { Search } from 'lucide-react';
import {
  usePathname,
  useRouter,
  useSearchParams,
  type ReadonlyURLSearchParams,
} from 'next/navigation';
import type { FC } from 'react';
import { useEffect, useState } from 'react';

const ALERTS_SEARCH_DEBOUNCE_MS = 400;

/** Routes where `q` is kept in the URL and synced from the search field (debounced). */
const SEARCH_QUERY_SYNC_PATHS = ['/alerts', '/dashboard'] as const;

function pathnameSyncsSearchQuery(pathname: string): boolean {
  return (SEARCH_QUERY_SYNC_PATHS as readonly string[]).includes(pathname);
}

type AlertsSearchFormInnerProps = {
  router: ReturnType<typeof useRouter>;
  pathname: string;
  searchParams: ReadonlyURLSearchParams;
  className?: string;
  placeholder?: string;
  inputClassName?: string;
};

const AlertsSearchFormInner: FC<AlertsSearchFormInnerProps> = ({
  router,
  pathname,
  searchParams,
  className,
  placeholder = 'Search alerts',
  inputClassName,
}) => {
  const syncSearchQuery = pathnameSyncsSearchQuery(pathname);
  const isAlertsPage = pathname === '/alerts';
  const isDashboardPage = pathname === '/dashboard';

  const urlQ = syncSearchQuery ? (searchParams.get('q') ?? '') : '';

  const [draft, setDraft] = useState(urlQ);

  useEffect(() => {
    const id = window.setTimeout(() => {
      if (!syncSearchQuery) {
        setDraft('');
        return;
      }
      setDraft(urlQ);
    }, 0);
    return () => window.clearTimeout(id);
  }, [syncSearchQuery, urlQ]);

  useEffect(() => {
    if (!syncSearchQuery) return;

    const term = draft.trim();
    const urlTrim = urlQ.trim();
    if (term === urlTrim) return;

    const id = window.setTimeout(() => {
      if (isAlertsPage) {
        const params = new URLSearchParams(searchParams.toString());
        if (term) params.set('q', term);
        else params.delete('q');
        params.set('page', '1');
        const qs = params.toString();
        router.replace(qs ? `/alerts?${qs}` : '/alerts');
        return;
      }
      if (isDashboardPage) {
        const params = new URLSearchParams();
        if (term) params.set('q', term);
        const qs = params.toString();
        router.replace(qs ? `/dashboard?${qs}` : '/dashboard');
      }
    }, ALERTS_SEARCH_DEBOUNCE_MS);

    return () => window.clearTimeout(id);
  }, [
    draft,
    isAlertsPage,
    isDashboardPage,
    router,
    searchParams,
    syncSearchQuery,
    urlQ,
  ]);

  const submitSearch = () => {
    const term = draft.trim();
    if (isAlertsPage) {
      const params = new URLSearchParams(searchParams.toString());
      if (term) params.set('q', term);
      else params.delete('q');
      params.set('page', '1');
      const qs = params.toString();
      router.replace(qs ? `/alerts?${qs}` : '/alerts');
      return;
    }
    if (isDashboardPage) {
      const params = new URLSearchParams();
      if (term) params.set('q', term);
      const qs = params.toString();
      router.replace(qs ? `/dashboard?${qs}` : '/dashboard');
      return;
    }
    if (!term) return;
    const params = new URLSearchParams({
      q: term,
      page: '1',
    });
    router.replace(`/alerts?${params.toString()}`);
  };

  return (
    <form
      className={className ?? 'min-w-0 flex-1'}
      role="search"
      onSubmit={e => {
        e.preventDefault();
        submitSearch();
      }}
    >
      <Input
        type="search"
        name="alert-search"
        placeholder={placeholder}
        leftIcon={<Search />}
        inputSize="sm"
        className={cn('h-10', inputClassName)}
        aria-label={placeholder}
        title="Results update shortly after you stop typing"
        value={draft}
        onChange={e => setDraft(e.target.value)}
      />
    </form>
  );
};

export type AlertsSearchFormProps = {
  className?: string;
  placeholder?: string;
  inputClassName?: string;
};

export const AlertsSearchForm: FC<AlertsSearchFormProps> = ({
  className,
  placeholder,
  inputClassName,
}) => {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  return (
    <AlertsSearchFormInner
      key={pathname}
      router={router}
      pathname={pathname}
      searchParams={searchParams}
      className={className}
      placeholder={placeholder}
      inputClassName={inputClassName}
    />
  );
};

export type AlertsSearchFormFallbackProps = {
  className?: string;
  placeholder?: string;
  inputClassName?: string;
};

export const AlertsSearchFormFallback: FC<AlertsSearchFormFallbackProps> = ({
  className,
  placeholder = 'Search alerts',
  inputClassName,
}) => (
  <div className={className ?? 'min-w-0 flex-1'}>
    <Input
      type="search"
      name="alert-search-fallback"
      placeholder={placeholder}
      leftIcon={<Search />}
      inputSize="sm"
      className={cn('h-10', inputClassName)}
      aria-label={placeholder}
      disabled
    />
  </div>
);
