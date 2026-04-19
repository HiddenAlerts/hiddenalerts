'use client';

import type { AlertItem } from '@/types/alert';
import { useCallback, useMemo, useState } from 'react';

export type AlertSort = 'recent' | 'oldest';

type UseAlertsListOptions = {
  items: AlertItem[];
  pageSize?: number;
};

export function useAlertsList({ items, pageSize = 5 }: UseAlertsListOptions) {
  const [category, setCategoryState] = useState('all');
  const [sort, setSortState] = useState<AlertSort>('recent');
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const list =
      category === 'all'
        ? [...items]
        : items.filter((a) => a.category === category);

    list.sort((a, b) => {
      const ta = new Date(a.occurredAt).getTime();
      const tb = new Date(b.occurredAt).getTime();
      return sort === 'recent' ? tb - ta : ta - tb;
    });

    return list;
  }, [items, category, sort]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const pageClamped = Math.min(page, totalPages);
  const pageItems = useMemo(() => {
    const start = (pageClamped - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, pageClamped, pageSize]);

  const setCategory = useCallback((value: string) => {
    setCategoryState(value);
    setPage(1);
  }, []);

  const setSort = useCallback((value: AlertSort) => {
    setSortState(value);
    setPage(1);
  }, []);

  return {
    category,
    setCategory,
    sort,
    setSort,
    page: pageClamped,
    setPage,
    totalPages,
    pageItems,
    totalCount: filtered.length,
  };
}
