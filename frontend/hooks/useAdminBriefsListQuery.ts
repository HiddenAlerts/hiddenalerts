'use client';

import { fetchAdminBriefsPage } from '@/lib/api/adminBriefs';
import { getAdminToken } from '@/lib/auth/adminSession';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

export const ADMIN_BRIEFS_PAGE_SIZE = 20;

export type AdminBriefsListFilters = {
  page: number;
  status: string;
  risk: string;
  category: string;
  search: string;
};

export function adminBriefsListQueryKey(filters: AdminBriefsListFilters) {
  return ['admin-briefs', 'list', filters] as const;
}

export function useAdminBriefsListQuery(filters: AdminBriefsListFilters) {
  const token = getAdminToken();
  const offset = (filters.page - 1) * ADMIN_BRIEFS_PAGE_SIZE;

  return useQuery({
    queryKey: adminBriefsListQueryKey(filters),
    queryFn: () =>
      fetchAdminBriefsPage(
        {
          limit: ADMIN_BRIEFS_PAGE_SIZE,
          offset,
          q: filters.search.trim() || undefined,
          status: filters.status !== 'all' ? filters.status : undefined,
          risk_level: filters.risk !== 'all' ? filters.risk : undefined,
          category: filters.category !== 'all' ? filters.category : undefined,
        },
        token!,
      ),
    placeholderData: keepPreviousData,
    enabled: Boolean(token),
  });
}
