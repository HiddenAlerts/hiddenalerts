'use client';

import {
  Button,
  ImageUpload,
  Input,
  PageHeader,
  RichTextEditor,
  Select,
  SourcesInput,
  Switch,
  TagsInput,
  Textarea,
} from '@/components';
import {
  ADMIN_CATEGORY_FORM_OPTIONS,
  ADMIN_CONFIDENCE_LEVEL_OPTIONS,
  ADMIN_RISK_LEVEL_FORM_OPTIONS,
  ADMIN_STATUS_FORM_OPTIONS,
} from '@/data/adminFilterOptions';
import { slugify } from '@/lib/utils';
import type { AdminBrief } from '@/types/admin';
import { Feather, FileEdit } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { type FC, type FormEvent, useState } from 'react';

const EMPTY_BRIEF: AdminBrief = {
  id: '',
  title: '',
  slug: '',
  category: ADMIN_CATEGORY_FORM_OPTIONS[0].value,
  riskScore: 0,
  riskLevel: 'low',
  primaryEntities: [],
  tags: [],
  featuredImage: undefined,
  executiveSummary: '',
  whyThisMatters: '',
  keySignals: '',
  riskAssessment: '',
  whatOthersMiss: '',
  implications: '',
  mainBrief: '',
  confidenceLevel: 'medium',
  sources: [],
  featured: false,
  status: 'draft',
  date: new Date().toISOString().slice(0, 10),
};

export type AdminBriefFormProps = {
  /** Pre-fills the form for the edit flow. */
  initial?: AdminBrief;
  /** Header title (defaults vary by mode). */
  title?: string;
  /** Header subtitle. */
  subtitle?: string;
  /** Where to navigate when the user saves/publishes/cancels. */
  returnHref?: string;
};

const SECTION_CLASSNAME =
  'border-border bg-background-alt space-y-5 rounded-lg border p-4 sm:p-6';

const SECTION_HEADING_CLASSNAME =
  'font-heading text-foreground text-sm font-semibold tracking-wide uppercase';

/**
 * Shared form for both creating and editing a brief. State is local — saving
 * is a no-op for now (UI only) and just navigates back to the briefs list.
 */
export const AdminBriefForm: FC<AdminBriefFormProps> = ({
  initial,
  title = 'Create / Edit Intelligence Brief',
  subtitle = 'All fields marked with * are required.',
  returnHref = '/admin/briefs',
}) => {
  const router = useRouter();
  const [brief, setBrief] = useState<AdminBrief>(initial ?? EMPTY_BRIEF);

  const update = <K extends keyof AdminBrief>(key: K, value: AdminBrief[K]) =>
    setBrief(prev => ({ ...prev, [key]: value }));

  function handleTitleChange(nextTitle: string) {
    setBrief(prev => ({ ...prev, title: nextTitle, slug: slugify(nextTitle) }));
  }

  function handleStatusChange(nextStatus: AdminBrief['status']) {
    setBrief(prev => ({
      ...prev,
      status: nextStatus,
      publishedDate:
        nextStatus === 'published'
          ? (prev.publishedDate ?? new Date().toISOString().slice(0, 10))
          : prev.publishedDate,
    }));
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    router.push(returnHref);
  }

  function handleSaveDraft() {
    router.push(returnHref);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <PageHeader
        title={title}
        subtitle={subtitle}
        icon={<FileEdit className="size-5" aria-hidden />}
        actions={
          <>
            <div className="flex items-center gap-2">
              <span className="text-muted text-sm font-medium">Status</span>
              <Select
                aria-label="Status"
                options={ADMIN_STATUS_FORM_OPTIONS}
                value={brief.status}
                onChange={e =>
                  handleStatusChange(e.target.value as AdminBrief['status'])
                }
                parentStyles="w-32"
              />
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleSaveDraft}
            >
              Save Draft
            </Button>
            <Button
              type="submit"
              size="sm"
              leftIcon={<Feather className="size-4" aria-hidden />}
            >
              Publish
            </Button>
          </>
        }
      />

      {/* 1. Basic Information */}
      <div className={SECTION_CLASSNAME}>
        <h2 className={SECTION_HEADING_CLASSNAME}>1. Basic Information</h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Input
            label="Title"
            required
            addAsterisk
            value={brief.title}
            onChange={e => handleTitleChange(e.target.value)}
            placeholder="Enter brief title"
            parentStyles="sm:col-span-2 lg:col-span-1"
          />
          <Select
            label="Category"
            required
            addAsterisk
            options={ADMIN_CATEGORY_FORM_OPTIONS}
            value={brief.category}
            onChange={e => update('category', e.target.value)}
          />
          <Input
            label="Risk Score (0-100)"
            required
            addAsterisk
            type="number"
            min={0}
            max={100}
            value={String(brief.riskScore)}
            onChange={e => update('riskScore', Number(e.target.value) || 0)}
          />
          <Select
            label="Risk Level"
            required
            addAsterisk
            options={ADMIN_RISK_LEVEL_FORM_OPTIONS}
            value={brief.riskLevel}
            onChange={e =>
              update('riskLevel', e.target.value as AdminBrief['riskLevel'])
            }
            valueClassName={
              brief.riskLevel === 'critical' || brief.riskLevel === 'high'
                ? 'text-danger'
                : undefined
            }
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TagsInput
            label="Primary Entities"
            required
            addAsterisk
            value={brief.primaryEntities}
            onChange={next => update('primaryEntities', next)}
            placeholder="Type and press Enter to add entities…"
          />
          <TagsInput
            label="Tags"
            value={brief.tags}
            onChange={next => update('tags', next)}
            placeholder="Type and press Enter to add tags…"
          />
        </div>

        <ImageUpload
          value={brief.featuredImage}
          onChange={url => update('featuredImage', url)}
        />
      </div>

      {/* 2. Intelligence Content */}
      <div className={SECTION_CLASSNAME}>
        <h2 className={SECTION_HEADING_CLASSNAME}>2. Intelligence Content</h2>

        <div className="grid gap-5 lg:grid-cols-2">
          <RichTextEditor
            label="Executive Summary"
            required
            addAsterisk
            value={brief.executiveSummary}
            onChange={html => update('executiveSummary', html)}
            placeholder="Provide a brief summary of the key intelligence…"
          />
          <RichTextEditor
            label="Why This Matters"
            required
            addAsterisk
            value={brief.whyThisMatters}
            onChange={html => update('whyThisMatters', html)}
            placeholder="Explain the significance and potential impact…"
          />
          <RichTextEditor
            label="Key Signals"
            required
            addAsterisk
            value={brief.keySignals}
            onChange={html => update('keySignals', html)}
            placeholder="Highlight the key indicators and warning signs…"
          />
          <RichTextEditor
            label="Risk Assessment"
            required
            addAsterisk
            value={brief.riskAssessment}
            onChange={html => update('riskAssessment', html)}
            placeholder="Assess the risk, potential impact and likelihood…"
          />
          <Textarea
            label="What Others Miss"
            value={brief.whatOthersMiss}
            onChange={e => update('whatOthersMiss', e.target.value)}
            placeholder="Key angles, behaviors or implications overlooked…"
            rows={3}
          />
          <Textarea
            label="Implications"
            value={brief.implications}
            onChange={e => update('implications', e.target.value)}
            placeholder="Potential impact and consequences…"
            rows={3}
          />
        </div>

        <RichTextEditor
          label="Main Intelligence Brief"
          required
          addAsterisk
          value={brief.mainBrief}
          onChange={html => update('mainBrief', html)}
          placeholder="Provide the full analysis, context, and details supporting this brief…"
          minHeightClassName="min-h-[220px]"
          showWordCount
        />
      </div>

      {/* 3. Publishing */}
      <div className={SECTION_CLASSNAME}>
        <h2 className={SECTION_HEADING_CLASSNAME}>3. Publishing</h2>

        <div className="grid gap-6 lg:grid-cols-2 lg:gap-x-8">
          <div className="space-y-4">
            <Select
              label="Confidence Level"
              required
              addAsterisk
              options={ADMIN_CONFIDENCE_LEVEL_OPTIONS}
              value={brief.confidenceLevel}
              onChange={e =>
                update(
                  'confidenceLevel',
                  e.target.value as AdminBrief['confidenceLevel'],
                )
              }
            />
            <SourcesInput
              value={brief.sources}
              onChange={next => update('sources', next)}
            />
          </div>

          <div className="space-y-4">
            <div>
              <span className="text-body mb-2 block text-sm font-medium">
                Featured Brief
              </span>
              <Switch
                checked={brief.featured}
                onChange={next => update('featured', next)}
                label="Display as the featured brief on the subscriber library"
              />
              <p className="text-muted mt-1.5 text-xs">
                Only one brief can be featured at a time.
              </p>
            </div>

            <Select
              label="Status"
              required
              addAsterisk
              options={ADMIN_STATUS_FORM_OPTIONS}
              value={brief.status}
              onChange={e =>
                handleStatusChange(e.target.value as AdminBrief['status'])
              }
            />
          </div>
        </div>

        <p className="border-border text-muted border-t pt-4 text-xs">
          Published Date will be set automatically when the brief is
          published.
        </p>
      </div>

      <div className="flex justify-end gap-2">
        <Link
          href={returnHref}
          className="text-muted hover:text-foreground inline-flex h-9 items-center px-4 text-sm font-medium"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
};
