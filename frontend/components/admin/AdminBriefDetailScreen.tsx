'use client';

import { Button, PageHeader, ScoreBadge, StatusTag } from '@/components';
import { findAdminBrief } from '@/data/adminMockBriefs';
import { formatAdminDate } from '@/lib/formatAdminDate';
import { ArrowLeft, Pencil } from 'lucide-react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { FC } from 'react';

import { AdminDetailField } from './AdminDetailField';

const TIME_HORIZON_LABEL = {
  'short-term': 'Short-term',
  'medium-term': 'Medium-term',
  'long-term': 'Long-term',
} as const;

const RISK_LEVEL_LABEL = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
} as const;

const STATUS_TONE = {
  published: 'success',
  draft: 'neutral',
} as const;

const STATUS_LABEL = {
  published: 'Published',
  draft: 'Draft',
} as const;

export type AdminBriefDetailScreenProps = {
  briefId: string;
};

const Chip: FC<{ children: string }> = ({ children }) => (
  <span className="bg-surface-muted text-body inline-flex items-center rounded-md px-2.5 py-1 text-xs">
    {children}
  </span>
);

export const AdminBriefDetailScreen: FC<AdminBriefDetailScreenProps> = ({
  briefId,
}) => {
  const brief = findAdminBrief(briefId);
  if (!brief) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={brief.title}
        subtitle={`/${brief.slug}`}
        actions={
          <>
            <Link
              href="/admin/briefs"
              className="text-muted hover:text-foreground inline-flex h-9 items-center gap-1.5 px-2 text-sm font-medium"
            >
              <ArrowLeft className="size-4" aria-hidden />
              Back
            </Link>
            <Link href={`/admin/briefs/${brief.id}/edit`}>
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
        <div className="grid gap-6 lg:grid-cols-2 lg:gap-x-8">
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <AdminDetailField label="Risk Score">
                <ScoreBadge score={brief.riskScore} />
              </AdminDetailField>
              <AdminDetailField label="Risk Level">
                {RISK_LEVEL_LABEL[brief.riskLevel]}
              </AdminDetailField>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <AdminDetailField label="Category">{brief.category}</AdminDetailField>
              <AdminDetailField label="Status">
                <StatusTag tone={STATUS_TONE[brief.status]}>
                  {STATUS_LABEL[brief.status]}
                </StatusTag>
              </AdminDetailField>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <AdminDetailField label="Date">
                {formatAdminDate(brief.date)}
              </AdminDetailField>
              <AdminDetailField label="Time Horizon">
                {TIME_HORIZON_LABEL[brief.timeHorizon]}
              </AdminDetailField>
            </div>

            <AdminDetailField label="Primary Entities">
              {brief.primaryEntities.length === 0 ? (
                '—'
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {brief.primaryEntities.map(entity => (
                    <Chip key={entity}>{entity}</Chip>
                  ))}
                </div>
              )}
            </AdminDetailField>

            <AdminDetailField label="Tags">
              {brief.tags.length === 0 ? (
                '—'
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {brief.tags.map(tag => (
                    <Chip key={tag}>{tag}</Chip>
                  ))}
                </div>
              )}
            </AdminDetailField>
          </div>

          <div className="space-y-5">
            <AdminDetailField
              label="Executive Summary"
              hint="(Public)"
              block
            >
              {brief.executiveSummary}
            </AdminDetailField>
            <AdminDetailField
              label="Key Intelligence"
              hint="(Subscribers Only)"
              block
            >
              {brief.keyIntelligence}
            </AdminDetailField>
            <AdminDetailField
              label="Risk Assessment"
              hint="(Subscribers Only)"
              block
            >
              {brief.riskAssessment}
            </AdminDetailField>
          </div>
        </div>
      </div>
    </div>
  );
};
