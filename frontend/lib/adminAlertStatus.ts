import type { StatusTone } from '@/components/ui/StatusTag';
import type { AdminAlertPublicationStatus } from '@/types/admin';

export type { AdminAlertPublicationStatus };

export type AdminAlertPublicationFields = {
  is_published: boolean;
  is_excluded: boolean;
  is_manual_hold: boolean;
  publish_decision: string;
  excluded_reason?: string | null;
};

export const ADMIN_ALERT_STATUS_TONE: Record<
  AdminAlertPublicationStatus,
  StatusTone
> = {
  published: 'success',
  excluded: 'danger',
  hold: 'warning',
  review: 'info',
  draft: 'neutral',
};

const ADMIN_ALERT_STATUS_LABEL: Record<AdminAlertPublicationStatus, string> = {
  published: 'Published',
  excluded: 'Excluded',
  hold: 'Hold',
  review: 'Review',
  draft: 'Draft',
};

/**
 * Resolve canonical Admin UI status.
 * 1. is_published → Published
 * 2. is_excluded or publish_decision=exclude → Excluded
 * 3. is_manual_hold or publish_decision=hold → Hold
 * 4. publish_decision=review → Review
 * 5. otherwise Draft
 */
export function resolveAdminAlertPublicationStatus(
  fields: AdminAlertPublicationFields,
): AdminAlertPublicationStatus {
  if (fields.is_published) return 'published';

  const decision = fields.publish_decision?.trim().toLowerCase() ?? '';

  if (fields.is_excluded || decision === 'exclude') return 'excluded';
  if (fields.is_manual_hold || decision === 'hold') return 'hold';
  if (decision === 'review') return 'review';

  return 'draft';
}

/** Status pill label; False Positive when excluded for manual_false_positive. */
export function formatAdminAlertPublicationStatusLabel(
  status: AdminAlertPublicationStatus,
  excludedReason?: string | null,
): string {
  if (
    status === 'excluded' &&
    excludedReason?.trim().toLowerCase() === 'manual_false_positive'
  ) {
    return 'False Positive';
  }
  return ADMIN_ALERT_STATUS_LABEL[status];
}

export function adminAlertStatusTone(
  status: AdminAlertPublicationStatus,
): StatusTone {
  return ADMIN_ALERT_STATUS_TONE[status];
}

/**
 * Approve visibility (confirmed product matrix).
 * Published: no. Review / Draft / Hold / Excluded: yes.
 * Additional: only when `is_relevant=true` (backend will not publish irrelevant).
 */
export function canAdminAlertApprove(
  status: AdminAlertPublicationStatus,
  isRelevant: boolean,
): boolean {
  if (!isRelevant) return false;
  return status !== 'published';
}

/**
 * False Positive visibility (confirmed product matrix).
 * Excluded / False Positive: no. Published / Review / Draft / Hold: yes.
 */
export function canAdminAlertMarkFalsePositive(
  status: AdminAlertPublicationStatus,
): boolean {
  return status !== 'excluded';
}

/** True when at least one of Approve / False Positive should render. */
export function hasAdminAlertReviewActions(
  status: AdminAlertPublicationStatus,
  isRelevant: boolean,
): boolean {
  return (
    canAdminAlertApprove(status, isRelevant) ||
    canAdminAlertMarkFalsePositive(status)
  );
}
