'use client';

import { Button, Select, Textarea } from '@/components';
import { useAdminAlertReviewMutation } from '@/hooks';
import { getApiErrorMessage } from '@/lib/api/queryError';
import type { AdminAlertDetail } from '@/types/admin';
import { type FC, useEffect, useState } from 'react';

/** Matches API `adjusted_risk_level` (`risk_level` values). */
const ADJUSTED_RISK_LEVEL_OPTIONS = [
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
] as const;

export type AdminAlertReviewActionsProps = {
  alert: AdminAlertDetail;
};

export const AdminAlertReviewActions: FC<AdminAlertReviewActionsProps> = ({
  alert,
}) => {
  const reviewMutation = useAdminAlertReviewMutation();
  const [editedSummary, setEditedSummary] = useState(alert.summary);
  const [adjustedRiskLevel, setAdjustedRiskLevel] = useState(alert.riskLevel);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackKind, setFeedbackKind] = useState<'success' | 'error'>('success');

  useEffect(() => {
    setEditedSummary(alert.summary);
    setAdjustedRiskLevel(alert.riskLevel);
  }, [alert.summary, alert.riskLevel]);

  const isPending = reviewMutation.isPending;

  async function submitApprovedOrFalsePositive(
    reviewStatus: 'approved' | 'false_positive',
  ) {
    setFeedback(null);

    try {
      await reviewMutation.mutateAsync({
        alertId: alert.id,
        payload: { review_status: reviewStatus },
      });

      setFeedbackKind('success');
      setFeedback(
        reviewStatus === 'approved'
          ? 'Alert approved and published.'
          : 'Alert marked as false positive and excluded.',
      );
    } catch (error) {
      setFeedbackKind('error');
      setFeedback(
        getApiErrorMessage(error, 'Unable to submit review. Please try again.'),
      );
    }
  }

  async function submitEdited() {
    setFeedback(null);

    const summary = editedSummary.trim();
    if (!summary) {
      setFeedbackKind('error');
      setFeedback('Edited summary is required.');
      return;
    }

    try {
      await reviewMutation.mutateAsync({
        alertId: alert.id,
        payload: {
          review_status: 'edited',
          edited_summary: summary,
          adjusted_risk_level: adjustedRiskLevel,
        },
      });

      setFeedbackKind('success');
      setFeedback('Alert summary and risk level updated.');
    } catch (error) {
      setFeedbackKind('error');
      setFeedback(
        getApiErrorMessage(error, 'Unable to submit review. Please try again.'),
      );
    }
  }

  return (
    <div className="border-border bg-background-alt space-y-4 rounded-lg border p-4 sm:p-6">
      <div>
        <h2 className="text-foreground text-base font-semibold">Review Actions</h2>
        <p className="text-muted mt-1 text-sm">
          Approve to publish, mark as false positive to exclude, or edit the
          summary and risk level.
        </p>
      </div>

      {alert.reviewStatus ? (
        <p className="text-body text-sm">
          Current review status:{' '}
          <span className="font-medium capitalize">
            {alert.reviewStatus.replaceAll('_', ' ')}
          </span>
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          disabled={isPending}
          onClick={() => void submitApprovedOrFalsePositive('approved')}
        >
          Approve
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={isPending}
          onClick={() => void submitApprovedOrFalsePositive('false_positive')}
        >
          Mark False Positive
        </Button>
      </div>

      <div className="border-border space-y-4 rounded-md border p-4">
        <p className="text-foreground text-sm font-medium">Edit</p>

        <div className="space-y-2">
          <label
            htmlFor="admin-alert-edited-summary"
            className="text-foreground text-sm font-medium"
          >
            Edited summary
          </label>
          <Textarea
            id="admin-alert-edited-summary"
            value={editedSummary}
            onChange={event => setEditedSummary(event.target.value)}
            rows={5}
            disabled={isPending}
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="admin-alert-adjusted-risk"
            className="text-foreground text-sm font-medium"
          >
            Adjusted risk level
          </label>
          <Select
            id="admin-alert-adjusted-risk"
            value={adjustedRiskLevel}
            onChange={event => setAdjustedRiskLevel(event.target.value)}
            options={[...ADJUSTED_RISK_LEVEL_OPTIONS]}
            disabled={isPending}
          />
        </div>

        <Button
          type="button"
          size="sm"
          disabled={isPending || editedSummary.trim().length === 0}
          onClick={() => void submitEdited()}
        >
          Save Edits
        </Button>
      </div>

      {feedback ? (
        <p
          className={
            feedbackKind === 'error' ? 'text-danger text-sm' : 'text-success text-sm'
          }
          role="status"
        >
          {feedback}
        </p>
      ) : null}
    </div>
  );
};
