'use client';

import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  ScoreBadge,
  StatusTag,
} from '@/components';
import { useAdminAlertDetailQuery } from '@/hooks';
import { getApiErrorMessage } from '@/lib/api/queryError';
import { formatAdminDate, formatAdminDateTime } from '@/lib/formatAdminDate';
import type { AdminAlertRiskExplanation } from '@/types/admin';
import { ArrowLeft, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import type { FC, ReactNode } from 'react';

import { AdminAlertReviewActions } from './AdminAlertReviewActions';
import { AdminDetailField } from './AdminDetailField';

const STATUS_TONE = {
  published: 'success',
  draft: 'neutral',
} as const;

const STATUS_LABEL = {
  published: 'Published',
  draft: 'Draft',
} as const;

export type AdminAlertDetailScreenProps = {
  alertId: string;
};

const Chip: FC<{ children: string }> = ({ children }) => (
  <span className="bg-surface-muted text-body inline-flex items-center rounded-md px-2.5 py-1 text-xs">
    {children}
  </span>
);

function formatEnumLabel(value?: string | null): string {
  if (!value?.trim()) return '—';
  return value
    .trim()
    .replaceAll('_', ' ')
    .replace(/\b\w/g, char => char.toUpperCase());
}

const FACTOR_LABELS: Record<string, string> = {
  sourceCredibility: 'Source credibility',
  financialImpact: 'Financial impact',
  victimScale: 'Victim scale',
  crossSource: 'Cross source',
  trendAcceleration: 'Trend acceleration',
};

function WhyThisDecisionPanel({
  explanation,
}: {
  explanation: AdminAlertRiskExplanation;
}) {
  const factorEntries = Object.entries(explanation.factors).filter(
    ([, value]) => typeof value === 'number',
  );

  return (
    <div className="border-border bg-background-alt space-y-4 rounded-lg border p-4 sm:p-6">
      <div>
        <h2 className="text-foreground text-base font-semibold">
          Why This Decision
        </h2>
        <p className="text-muted mt-1 text-sm">
          Internal moderation context from the publishing policy pipeline.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <AdminDetailField label="Score (100)">
          {explanation.score100}
        </AdminDetailField>
        <AdminDetailField label="Risk Band">
          {formatEnumLabel(explanation.riskBand)}
        </AdminDetailField>
        <AdminDetailField label="Publication Decision">
          {formatEnumLabel(explanation.publicationDecision)}
        </AdminDetailField>
        <AdminDetailField label="Publication Reason">
          {formatEnumLabel(explanation.publicationReason)}
        </AdminDetailField>
        <AdminDetailField label="Pending Review Reason">
          {formatEnumLabel(explanation.pendingReviewReason)}
        </AdminDetailField>
        <AdminDetailField label="Source Credibility">
          {explanation.sourceCredibility}
        </AdminDetailField>
      </div>

      {factorEntries.length > 0 ? (
        <AdminDetailField label="Score Factors">
          <ul className="space-y-1">
            {factorEntries.map(([key, value]) => (
              <li key={key} className="text-body text-sm">
                {FACTOR_LABELS[key] ?? key}: {value}
              </li>
            ))}
          </ul>
        </AdminDetailField>
      ) : null}
    </div>
  );
}

function DetailSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="border-border bg-background-alt rounded-lg border p-4 sm:p-6">
      <h2 className="text-foreground mb-4 text-base font-semibold">{title}</h2>
      {children}
    </div>
  );
}

export const AdminAlertDetailScreen: FC<AdminAlertDetailScreenProps> = ({
  alertId,
}) => {
  const { data: alert, isPending, isError, error, refetch } =
    useAdminAlertDetailQuery(alertId);

  if (isPending) {
    return <LoadingState label="Loading alert…" />;
  }

  if (isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(
          error,
          'Unable to load this alert. Please try again.',
        )}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!alert) {
    return (
      <EmptyState
        title="Alert not found"
        description="This alert is not available right now."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={alert.title}
        subtitle={`${alert.category} · ${alert.sourceName}`}
        actions={
          <Link
            href="/admin/alerts"
            className="text-muted hover:text-foreground inline-flex h-9 items-center gap-1.5 px-2 text-sm font-medium"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Back
          </Link>
        }
      />

      <DetailSection title="Alert Overview">
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <AdminDetailField label="Risk Score">
              <ScoreBadge
                score={alert.riskScore}
                riskLevel={alert.riskLevel}
                riskBand={alert.riskBand}
              />
            </AdminDetailField>
            <AdminDetailField label="Risk Band">
              {formatEnumLabel(alert.riskBand)}
            </AdminDetailField>
            <AdminDetailField label="Publication Status">
              <StatusTag tone={STATUS_TONE[alert.status]}>
                {STATUS_LABEL[alert.status]}
              </StatusTag>
            </AdminDetailField>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <AdminDetailField label="Category">{alert.category}</AdminDetailField>
            <AdminDetailField label="Publish Decision">
              {formatEnumLabel(alert.publishDecision)}
            </AdminDetailField>
            <AdminDetailField label="Pending Review Reason">
              {formatEnumLabel(alert.pendingReviewReason)}
            </AdminDetailField>
            <AdminDetailField label="Source">{alert.sourceName}</AdminDetailField>
            <AdminDetailField label="Publication State Source">
              {formatEnumLabel(alert.publicationStateSource)}
            </AdminDetailField>
            <AdminDetailField label="Review Status">
              {formatEnumLabel(alert.reviewStatus)}
            </AdminDetailField>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <AdminDetailField label="Source Published">
              {formatAdminDate(alert.date)}
            </AdminDetailField>
            <AdminDetailField label="Processed At">
              {formatAdminDateTime(alert.processedAt)}
            </AdminDetailField>
            <AdminDetailField label="State Updated At">
              {alert.publicationStateUpdatedAt
                ? formatAdminDateTime(alert.publicationStateUpdatedAt)
                : '—'}
            </AdminDetailField>
          </div>

          <AdminDetailField label="Source URL">
            {alert.itemUrl ? (
              <a
                href={alert.itemUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1 underline-offset-2 hover:underline"
              >
                Open source
                <ExternalLink className="size-3.5" aria-hidden />
              </a>
            ) : (
              '—'
            )}
          </AdminDetailField>

          <AdminDetailField label="Summary" block>
            {alert.summary || '—'}
          </AdminDetailField>

          <AdminDetailField label="Matched Keywords">
            {alert.tags.length === 0 ? (
              '—'
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {alert.tags.map(tag => (
                  <Chip key={tag}>{tag}</Chip>
                ))}
              </div>
            )}
          </AdminDetailField>

          {alert.eventTitle ? (
            <AdminDetailField label="Linked Event">
              {alert.eventTitle}
              {alert.eventId ? ` (ID ${alert.eventId})` : ''}
            </AdminDetailField>
          ) : null}
        </div>
      </DetailSection>

      {alert.riskExplanation ? (
        <WhyThisDecisionPanel explanation={alert.riskExplanation} />
      ) : null}

      <AdminAlertReviewActions alert={alert} />
    </div>
  );
};
