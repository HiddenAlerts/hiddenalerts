'use client';

import { submitAdminAlertReview } from '@/lib/api/adminAlerts';
import { getAdminToken } from '@/lib/auth/adminSession';
import type { AdminAlertReviewPayload } from '@/types/adminAlertsApi';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { adminAlertDetailQueryKey } from './useAdminAlertDetailQuery';

function requireAdminToken(): string {
  const token = getAdminToken();
  if (!token) throw new Error('You must be signed in as an admin to do this.');
  return token;
}

export type SubmitAdminAlertReviewInput = {
  alertId: string;
  payload: AdminAlertReviewPayload;
};

export function useAdminAlertReviewMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ alertId, payload }: SubmitAdminAlertReviewInput) =>
      submitAdminAlertReview(alertId, payload, requireAdminToken()),
    onSuccess: (_data, { alertId }) => {
      void queryClient.invalidateQueries({
        queryKey: adminAlertDetailQueryKey(alertId),
      });
      void queryClient.invalidateQueries({ queryKey: ['admin-alerts', 'list'] });
    },
  });
}
