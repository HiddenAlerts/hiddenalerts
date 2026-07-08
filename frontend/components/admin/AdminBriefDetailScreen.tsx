'use client';

import { Button, PageHeader, ScoreBadge, StatusTag } from '@/components';
import { findAdminBrief } from '@/data/adminMockBriefs';
import { formatAdminDate } from '@/lib/formatAdminDate';
import { ArrowLeft, Pencil } from 'lucide-react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { FC } from 'react';

import { AdminDetailField } from './AdminDetailField';

const RISK_LEVEL_LABEL = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
} as const;

const CONFIDENCE_LEVEL_LABEL = {
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

/** Renders stored rich-text HTML content inside a bordered block. */
const RichTextBlock: FC<{ label: string; html: string }> = ({
  label,
  html,
}) => (
  <div className="flex flex-col gap-1.5">
    <p className="text-foreground text-sm font-medium">{label}</p>
    {html ? (
      <div
        className="text-body bg-surface/40 border-border min-h-[6rem] max-w-none rounded-md border px-3 py-2.5 text-sm leading-relaxed [&_h1]:text-foreground [&_h1]:mt-3 [&_h1]:mb-1.5 [&_h1]:text-2xl [&_h1]:font-semibold [&_h2]:text-foreground [&_h2]:mt-3 [&_h2]:mb-1.5 [&_h2]:text-xl [&_h2]:font-semibold [&_h3]:text-foreground [&_h3]:mt-2.5 [&_h3]:mb-1 [&_h3]:text-lg [&_h3]:font-semibold [&_h4]:text-foreground [&_h4]:mt-2 [&_h4]:mb-1 [&_h4]:text-base [&_h4]:font-semibold [&_h5]:text-foreground [&_h5]:mt-2 [&_h5]:mb-1 [&_h5]:text-sm [&_h5]:font-semibold [&_h6]:text-foreground [&_h6]:mt-2 [&_h6]:mb-1 [&_h6]:text-xs [&_h6]:font-semibold [&_h6]:tracking-wide [&_h6]:uppercase [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-1 [&_ul]:list-disc [&_ul]:pl-5"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    ) : (
      <div className="text-body bg-surface/40 border-border flex min-h-[6rem] items-center rounded-md border px-3 py-2.5 text-sm">
        <span className="text-muted italic">No content provided.</span>
      </div>
    )}
  </div>
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
            {brief.featuredImage ? (
              <AdminDetailField label="Featured Image">
                {/* Local preview URL; no remote host to optimize via next/image. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={brief.featuredImage}
                  alt=""
                  className="border-border aspect-video w-full max-w-sm rounded-md border object-cover"
                />
              </AdminDetailField>
            ) : null}

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
              <AdminDetailField label="Confidence Level">
                {CONFIDENCE_LEVEL_LABEL[brief.confidenceLevel]}
              </AdminDetailField>
              <AdminDetailField label="Featured">
                {brief.featured ? (
                  <StatusTag tone="success">Featured</StatusTag>
                ) : (
                  '—'
                )}
              </AdminDetailField>
            </div>

            <AdminDetailField label="Published Date">
              {brief.publishedDate
                ? formatAdminDate(brief.publishedDate)
                : '—'}
            </AdminDetailField>

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

            <AdminDetailField label="Sources">
              {brief.sources.length === 0 ? (
                '—'
              ) : (
                <ol className="list-decimal space-y-1 pl-4">
                  {brief.sources.map((source, index) => (
                    <li key={index}>{source}</li>
                  ))}
                </ol>
              )}
            </AdminDetailField>
          </div>

          <div className="space-y-5">
            <RichTextBlock
              label="Executive Summary"
              html={brief.executiveSummary}
            />
            <RichTextBlock
              label="Why This Matters"
              html={brief.whyThisMatters}
            />
            <RichTextBlock label="Key Signals" html={brief.keySignals} />
            <RichTextBlock
              label="Risk Assessment"
              html={brief.riskAssessment}
            />
            <AdminDetailField label="What Others Miss" block>
              {brief.whatOthersMiss}
            </AdminDetailField>
            <AdminDetailField label="Implications" block>
              {brief.implications}
            </AdminDetailField>
            <RichTextBlock
              label="Main Intelligence Brief"
              html={brief.mainBrief}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
