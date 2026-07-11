'use client';

import { fetchAdminBriefBySlug } from '@/lib/api/adminBriefs';
import { getAdminToken } from '@/lib/auth/adminSession';
import { useQuery } from '@tanstack/react-query';

export function adminBriefBySlugQueryKey(slug: string) {
  return ['admin-briefs', 'detail-by-slug', slug] as const;
}

export function useAdminBriefBySlugQuery(slug: string) {
  const token = getAdminToken();

  return useQuery({
    queryKey: adminBriefBySlugQueryKey(slug),
    queryFn: () => fetchAdminBriefBySlug(slug, token!),
    enabled: Boolean(slug) && Boolean(token),
  });
}
