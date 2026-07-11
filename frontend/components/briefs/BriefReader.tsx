'use client';

import { StatusTag } from '@/components';
import { CONFIDENCE_LEVEL_LABEL, RISK_LEVEL_LABEL } from '@/lib/briefDetail';
import { formatBriefDate } from '@/lib/briefs';
import { TIPTAP_CONTENT_CLASSNAME } from '@/lib/tiptapContentStyles';
import { cn } from '@/lib/utils';
import type { BriefDetail } from '@/types/briefs';
import { ArrowLeft, Eye, FileText, Share2, X } from 'lucide-react';
import Link from 'next/link';
import { type FC } from 'react';
import { toast } from 'sonner';

import { BriefCover } from './BriefCover';
import { BriefRiskTag } from './BriefRiskTag';
import { BriefScoreGauge } from './BriefScoreGauge';

const TAG_PALETTE = [
  'bg-info/15 text-info border-info/30',
  'bg-warning/15 text-warning border-warning/30',
  'bg-danger/15 text-danger border-danger/30',
  'bg-success/15 text-success border-success/30',
  'border-border text-body bg-surface-muted',
];

/** Deterministic color rotation so tags read as distinct without per-tag color data. */
function tagTone(tag: string): string {
  let hash = 0;
  for (let i = 0; i < tag.length; i += 1) hash = (hash * 31 + tag.charCodeAt(i)) >>> 0;
  return TAG_PALETTE[hash % TAG_PALETTE.length];
}

const RichSection: FC<{ title: string; html: string }> = ({ title, html }) => (
  <div>
    <h2 className="font-heading text-foreground mb-2 text-lg font-semibold">
      {title}
    </h2>
    {html ? (
      <div
        className={cn('text-body max-w-none text-sm leading-relaxed', TIPTAP_CONTENT_CLASSNAME)}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    ) : (
      <p className="text-muted text-sm italic">No content provided.</p>
    )}
  </div>
);

const MetaRow: FC<{ label: string; value: string; valueClassName?: string }> = ({
  label,
  value,
  valueClassName,
}) => (
  <div className="flex items-center justify-between gap-3 px-4 py-3">
    <span className="text-muted text-sm">{label}</span>
    <span className={cn('text-foreground text-sm font-semibold', valueClassName)}>
      {value}
    </span>
  </div>
);

export type BriefReaderProps = {
  brief: BriefDetail;
  /** 'subscriber' shows Back/Share; 'preview' shows an admin banner + Close; 'none' shows neither (caller provides its own chrome). */
  topBar?: 'subscriber' | 'preview' | 'none';
  onClose?: () => void;
  backHref?: string;
};

/**
 * Renders a brief exactly as a subscriber would read it. Shared by the
 * subscriber detail page, the admin detail page, and the admin form's live
 * "Preview" overlay — only `topBar` changes between them.
 */
export const BriefReader: FC<BriefReaderProps> = ({
  brief,
  topBar = 'subscriber',
  onClose,
  backHref = '/briefs',
}) => {
  async function handleShare() {
    const url =
      typeof window !== 'undefined'
        ? `${window.location.origin}/briefs/${brief.slug}`
        : `/briefs/${brief.slug}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success('Link copied to clipboard');
    } catch {
      toast.error('Could not copy link');
    }
  }

  const riskLabel = RISK_LEVEL_LABEL[brief.riskLevel];
  const isHighRisk = brief.riskLevel === 'critical' || brief.riskLevel === 'high';

  return (
    <div>
      {topBar === 'subscriber' ? (
        <div className="border-border flex items-center justify-between gap-3 border-b px-4 py-3 sm:px-6">
          <Link
            href={backHref}
            className="text-muted hover:text-foreground inline-flex items-center gap-1.5 text-sm font-medium"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Back to Library
          </Link>
          <button
            type="button"
            onClick={handleShare}
            className="text-muted hover:text-foreground inline-flex items-center gap-1.5 text-sm font-medium"
          >
            <Share2 className="size-4" aria-hidden />
            Share
          </button>
        </div>
      ) : null}

      {topBar === 'preview' ? (
        <div className="border-border bg-surface-muted/40 flex items-center justify-between gap-3 border-b px-4 py-3 sm:px-6">
          <span className="text-info inline-flex items-center gap-1.5 text-xs font-semibold tracking-wide uppercase">
            <Eye className="size-4" aria-hidden />
            How the brief appears to subscribers
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close preview"
            className="text-muted hover:text-foreground hover:bg-surface-muted inline-flex size-8 items-center justify-center rounded-md"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
      ) : null}

      <div className="space-y-6 p-4 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="bg-info inline-flex items-center rounded-sm px-2 py-0.5 text-[0.65rem] font-bold tracking-wide text-white uppercase">
                {brief.category}
              </span>
              <BriefRiskTag riskLabel={riskLabel} />
              {brief.status === 'draft' ? (
                <StatusTag tone="neutral">Draft</StatusTag>
              ) : null}
              {brief.status === 'archived' ? (
                <StatusTag tone="warning">Archived</StatusTag>
              ) : null}
            </div>

            <h1 className="font-heading text-foreground text-2xl font-bold tracking-tight sm:text-3xl">
              {brief.title}
            </h1>

            <p className="text-muted text-xs">
              {brief.publishedDate
                ? `Published: ${formatBriefDate(brief.publishedDate)}`
                : 'Not yet published'}
              {' · '}
              {brief.supportingAlerts.length} Sources
            </p>

            {brief.primaryEntities.length > 0 ? (
              <div className="flex flex-wrap items-center gap-1.5 text-sm">
                <span className="text-muted">Entities:</span>
                {brief.primaryEntities.map(entity => (
                  <span
                    key={entity}
                    className="bg-surface-muted text-body rounded-md px-2 py-0.5 text-xs"
                  >
                    {entity}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <BriefScoreGauge score={brief.riskScore} />
        </div>

        {brief.featuredImage ? (
          // Local/uploaded image URL; no remote host to optimize via next/image.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={brief.featuredImage}
            alt=""
            className="aspect-[21/9] w-full rounded-lg object-cover"
          />
        ) : (
          <BriefCover theme={brief.coverTheme} className="aspect-[21/9] w-full rounded-lg" />
        )}

        <div className="grid gap-6 lg:grid-cols-3 lg:gap-8">
          <div className="space-y-6 lg:col-span-2">
            <RichSection title="Executive Summary" html={brief.executiveSummary} />
            <RichSection title="Why This Matters" html={brief.whyThisMatters} />
            <RichSection title="Key Signals" html={brief.keySignals} />
            <RichSection title="Risk Assessment" html={brief.riskAssessment} />
            <RichSection title="What Others Miss" html={brief.whatOthersMiss} />
            <RichSection title="Implications" html={brief.implications} />
            <RichSection title="Main Intelligence Brief" html={brief.mainBrief} />
          </div>

          <div className="space-y-6">
            <div className="border-border divide-border divide-y overflow-hidden rounded-lg border">
              <MetaRow label="Category" value={brief.category} />
              <MetaRow
                label="Risk Level"
                value={riskLabel}
                valueClassName={isHighRisk ? 'text-danger' : undefined}
              />
              <MetaRow
                label="Confidence Level"
                value={CONFIDENCE_LEVEL_LABEL[brief.confidenceLevel]}
              />
              <MetaRow label="Sources" value={String(brief.supportingAlerts.length)} />
            </div>

            {brief.tags.length > 0 ? (
              <div>
                <p className="text-foreground mb-2 text-sm font-semibold">Tags</p>
                <div className="flex flex-wrap gap-1.5">
                  {brief.tags.map(tag => (
                    <span
                      key={tag}
                      className={cn(
                        'rounded-md border px-2 py-0.5 text-xs font-medium',
                        tagTone(tag),
                      )}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {brief.supportingAlerts.length > 0 ? (
              <div>
                <p className="text-foreground mb-2 flex items-center gap-1.5 text-sm font-semibold">
                  <FileText className="size-4" aria-hidden />
                  Sources
                </p>
                <ol className="text-body list-decimal space-y-1 pl-4 text-sm">
                  {brief.supportingAlerts.map((alert, index) => (
                    <li key={index}>
                      <a
                        href={alert.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-primary-400 underline"
                      >
                        {alert.title || alert.url}
                      </a>
                    </li>
                  ))}
                </ol>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};
