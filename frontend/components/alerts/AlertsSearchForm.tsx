'use client';

import { Input } from '@/components';
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

type AlertsSearchFormInnerProps = {
  router: ReturnType<typeof useRouter>;
  pathname: string;
  searchParams: ReadonlyURLSearchParams;
  className?: string;
};

const AlertsSearchFormInner: FC<AlertsSearchFormInnerProps> = ({
  router,
  pathname,
  searchParams,
  className,
}) => {
  const isAlertsPage = pathname === '/alerts';
  const urlQ = isAlertsPage ? (searchParams.get('q') ?? '') : '';

  const [draft, setDraft] = useState(urlQ);

  useEffect(() => {
    const id = window.setTimeout(() => {
      if (!isAlertsPage) {
        setDraft('');
        return;
      }
      setDraft(urlQ);
    }, 0);
    return () => window.clearTimeout(id);
  }, [isAlertsPage, urlQ]);

  useEffect(() => {
    if (!isAlertsPage) return;

    const term = draft.trim();
    const urlTrim = urlQ.trim();
    if (term === urlTrim) return;

    const id = window.setTimeout(() => {
      const params = new URLSearchParams(searchParams.toString());
      if (term) params.set('q', term);
      else params.delete('q');
      params.set('page', '1');
      const qs = params.toString();
      router.replace(qs ? `/alerts?${qs}` : '/alerts');
    }, ALERTS_SEARCH_DEBOUNCE_MS);

    return () => window.clearTimeout(id);
  }, [draft, isAlertsPage, router, searchParams, urlQ]);

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
        placeholder="Search alerts"
        leftIcon={<Search />}
        inputSize="sm"
        className="h-10"
        aria-label="Search alerts"
        title="Results update shortly after you stop typing"
        value={draft}
        onChange={e => setDraft(e.target.value)}
      />
    </form>
  );
};

export const AlertsSearchForm: FC<{ className?: string }> = ({ className }) => {
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
    />
  );
};

export const AlertsSearchFormFallback: FC<{ className?: string }> = ({
  className,
}) => (
  <div className={className ?? 'min-w-0 flex-1'}>
    <Input
      type="search"
      name="alert-search-fallback"
      placeholder="Search alerts"
      leftIcon={<Search />}
      inputSize="sm"
      className="h-10"
      aria-label="Search alerts"
      disabled
    />
  </div>
);
