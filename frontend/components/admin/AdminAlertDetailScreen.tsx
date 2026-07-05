'use client';

import { Button, PageHeader, ScoreBadge, StatusTag } from '@/components';
import { findAdminAlert } from '@/data/adminMockAlerts';
import { findAdminBrief } from '@/data/adminMockBriefs';
import { formatAdminDate } from '@/lib/formatAdminDate';
import { ArrowLeft, Pencil } from 'lucide-react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { FC } from 'react';

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

export const AdminAlertDetailScreen: FC<AdminAlertDetailScreenProps> = ({
  alertId,
}) => {
  const alert = findAdminAlert(alertId);
  if (!alert) {
    notFound();
  }

  const linkedBrief = alert.briefId ? findAdminBrief(alert.briefId) : undefined;

  return (
    <div className="space-y-6">
      <PageHeader
        title={alert.title}
        subtitle={alert.category}
        actions={
          <>
            <Link
              href="/admin/alerts"
              className="text-muted hover:text-foreground inline-flex h-9 items-center gap-1.5 px-2 text-sm font-medium"
            >
              <ArrowLeft className="size-4" aria-hidden />
              Back
            </Link>
            <Link href={`/admin/alerts/${alert.id}/edit`}>
              <Button
                type="button"
                size="sm"
                leftIcon={<Pencil className="size-4" aria-hidden />}
              >
                Edit
              </Button>
            </Link>
          </>
        }
      />

      <div className="border-border bg-background-alt rounded-lg border p-4 sm:p-6">
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <AdminDetailField label="Risk Score">
              <ScoreBadge score={alert.riskScore} />
            </AdminDetailField>
            <AdminDetailField label="Category">
              {alert.category}
            </AdminDetailField>
            <AdminDetailField label="Status">
              <StatusTag tone={STATUS_TONE[alert.status]}>
                {STATUS_LABEL[alert.status]}
              </StatusTag>
            </AdminDetailField>
          </div>

          <AdminDetailField label="Date">
            {formatAdminDate(alert.date)}
          </AdminDetailField>

          <AdminDetailField label="Summary" block>
            {alert.summary}
          </AdminDetailField>

          <AdminDetailField label="Link to Brief" hint="(optional)">
            {linkedBrief ? (
              <Link
                href={`/admin/briefs/${linkedBrief.id}`}
                className="text-primary-400 hover:text-primary-300 underline-offset-2 hover:underline"
              >
                {linkedBrief.title}
              </Link>
            ) : (
              '—'
            )}
          </AdminDetailField>

          <AdminDetailField label="Tags">
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
        </div>
      </div>
    </div>
  );
};
