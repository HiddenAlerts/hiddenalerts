'use client';

import {
  archiveAdminBrief,
  createAdminBrief,
  featureAdminBrief,
  publishAdminBrief,
  removeAdminBriefImage,
  unfeatureAdminBrief,
  updateAdminBrief,
  uploadAdminBriefImage,
} from '@/lib/api/adminBriefs';
import { getAdminToken } from '@/lib/auth/adminSession';
import type { AdminBrief } from '@/types/admin';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { adminBriefBySlugQueryKey } from './useAdminBriefBySlugQuery';

function requireAdminToken(): string {
  const token = getAdminToken();
  if (!token) throw new Error('You must be signed in as an admin to do this.');
  return token;
}

/** Invalidates both the list and the (now-stale) detail entry for a brief. */
function useInvalidateAdminBriefQueries() {
  const queryClient = useQueryClient();
  return (brief: AdminBrief) => {
    void queryClient.invalidateQueries({ queryKey: ['admin-briefs', 'list'] });
    void queryClient.invalidateQueries({
      queryKey: adminBriefBySlugQueryKey(brief.slug),
    });
  };
}

export type SaveAdminBriefInput = {
  brief: AdminBrief;
  /** A newly-picked local file to upload after saving, if any. */
  imageFile?: File;
  /** True when the user removed a previously-set image. */
  removeImage?: boolean;
};

/**
 * Composite save: create-or-update the brief, then conditionally upload or
 * remove its featured image — one loading state and one error surface for
 * what is, from the admin's perspective, a single "Save" action.
 */
export function useSaveAdminBriefMutation() {
  const invalidate = useInvalidateAdminBriefQueries();

  return useMutation({
    mutationFn: async ({ brief, imageFile, removeImage }: SaveAdminBriefInput) => {
      const token = requireAdminToken();
      let saved = brief.id
        ? await updateAdminBrief(brief.id, brief, token)
        : await createAdminBrief(brief, token);

      if (imageFile) {
        saved = await uploadAdminBriefImage(saved.id, imageFile, token);
      } else if (removeImage) {
        saved = await removeAdminBriefImage(saved.id, token);
      }

      return saved;
    },
    onSuccess: saved => invalidate(saved),
  });
}

export function usePublishAdminBriefMutation() {
  const invalidate = useInvalidateAdminBriefQueries();
  return useMutation({
    mutationFn: (briefId: string) => publishAdminBrief(briefId, requireAdminToken()),
    onSuccess: saved => invalidate(saved),
  });
}

export function useArchiveAdminBriefMutation() {
  const invalidate = useInvalidateAdminBriefQueries();
  return useMutation({
    mutationFn: (briefId: string) => archiveAdminBrief(briefId, requireAdminToken()),
    onSuccess: saved => invalidate(saved),
  });
}

export type SetFeaturedInput = { briefId: string; featured: boolean };

/** Toggles the featured state via the dedicated feature/unfeature endpoints. */
export function useSetAdminBriefFeaturedMutation() {
  const invalidate = useInvalidateAdminBriefQueries();
  return useMutation({
    mutationFn: ({ briefId, featured }: SetFeaturedInput) => {
      const token = requireAdminToken();
      return featured
        ? featureAdminBrief(briefId, token)
        : unfeatureAdminBrief(briefId, token);
    },
    onSuccess: saved => invalidate(saved),
  });
}
