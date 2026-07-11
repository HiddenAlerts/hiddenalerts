'use client';

import { fetchAdminAlertsPage } from '@/lib/api/adminAlerts';
import { getAdminToken } from '@/lib/auth/adminSession';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

export const ADMIN_ALERTS_PAGE_SIZE = 20;

export type AdminAlertsListFilters = {
  page: number;
  status: string;
  risk: string;
  category: string;
  search: string;
};

export function adminAlertsListQueryKey(filters: AdminAlertsListFilters) {
  return ['admin-alerts', 'list', filters] as const;
}

function mapStatusFilter(
  status: string,
): Pick<Parameters<typeof fetchAdminAlertsPage>[0], 'is_published'> {
  if (status === 'published') return { is_published: true };
  if (status === 'draft') return { is_published: false };
  return {};
}

function mapRiskFilter(risk: string): Pick<
  Parameters<typeof fetchAdminAlertsPage>[0],
  'risk_level' | 'risk_band'
> {
  if (risk === 'critical') return { risk_band: 'critical' };
  if (risk === 'high') return { risk_level: 'high' };
  if (risk === 'medium') return { risk_level: 'medium' };
  if (risk === 'low') return { risk_level: 'low' };
  return {};
}

export function useAdminAlertsListQuery(filters: AdminAlertsListFilters) {
  const token = getAdminToken();
  const offset = (filters.page - 1) * ADMIN_ALERTS_PAGE_SIZE;

  return useQuery({
    queryKey: adminAlertsListQueryKey(filters),
    queryFn: () =>
      fetchAdminAlertsPage(
        {
          limit: ADMIN_ALERTS_PAGE_SIZE,
          offset,
          keyword: filters.search.trim() || undefined,
          category: filters.category !== 'all' ? filters.category : undefined,
          ...mapStatusFilter(filters.status),
          ...mapRiskFilter(filters.risk),
        },
        token!,
      ),
    placeholderData: keepPreviousData,
    enabled: Boolean(token),
  });
}
