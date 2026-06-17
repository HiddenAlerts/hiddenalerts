'use client';

import {
  Button,
  Input,
  PageHeader,
  Select,
  TagsInput,
  Textarea,
} from '@/components';
import {
  ADMIN_CATEGORY_FORM_OPTIONS,
  ADMIN_RISK_LEVEL_FORM_OPTIONS,
  ADMIN_TIME_HORIZON_OPTIONS,
} from '@/data/adminFilterOptions';
import { cn } from '@/lib/utils';
import type { AdminBrief } from '@/types/admin';
import { Feather } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { type FC, type FormEvent, useState } from 'react';

const EMPTY_BRIEF: AdminBrief = {
  id: '',
  title: '',
  slug: '',
  riskScore: 0,
  riskLevel: 'low',
  category: ADMIN_CATEGORY_FORM_OPTIONS[0].value,
  date: new Date().toISOString().slice(0, 10),
  timeHorizon: 'short-term',
  primaryEntities: [],
  tags: [],
  executiveSummary: '',
  keyIntelligence: '',
  riskAssessment: '',
  status: 'draft',
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

/**
 * Shared form for both creating and editing a brief. State is local — saving
 * is a no-op for now (UI only) and just navigates back to the briefs list.
 */
export const AdminBriefForm: FC<AdminBriefFormProps> = ({
  initial,
  title = 'Create / Edit Brief',
  subtitle = 'Add or update intelligence brief',
  returnHref = '/admin/briefs',
}) => {
  const router = useRouter();
  const [brief, setBrief] = useState<AdminBrief>(initial ?? EMPTY_BRIEF);

  const update = <K extends keyof AdminBrief>(key: K, value: AdminBrief[K]) =>
    setBrief(prev => ({ ...prev, [key]: value }));

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
        actions={
          <>
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

      <div
        className={cn(
          'border-border bg-background-alt rounded-lg border p-4 sm:p-6',
        )}
      >
        <div className="grid gap-6 lg:grid-cols-2 lg:gap-x-8">
          <div className="space-y-4">
            <Input
              label="Title"
              required
              addAsterisk
              value={brief.title}
              onChange={e => update('title', e.target.value)}
              placeholder="Brief title"
            />

            <div>
              <Input
                label="Slug"
                required
                addAsterisk
                value={brief.slug}
                onChange={e => update('slug', e.target.value)}
                placeholder="brief-slug"
              />
              <p className="text-muted mt-1.5 text-xs">
                This will be the URL of the brief
              </p>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Risk Score"
                required
                addAsterisk
                type="number"
                min={0}
                max={100}
                value={String(brief.riskScore)}
                onChange={e =>
                  update('riskScore', Number(e.target.value) || 0)
                }
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
                  brief.riskLevel === 'high' ? 'text-danger' : undefined
                }
              />
            </div>

            <Select
              label="Category"
              required
              addAsterisk
              options={ADMIN_CATEGORY_FORM_OPTIONS}
              value={brief.category}
              onChange={e => update('category', e.target.value)}
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Date"
                required
                addAsterisk
                type="date"
                value={brief.date}
                onChange={e => update('date', e.target.value)}
              />
              <Select
                label="Time Horizon"
                options={ADMIN_TIME_HORIZON_OPTIONS}
                value={brief.timeHorizon}
                onChange={e =>
                  update(
                    'timeHorizon',
                    e.target.value as AdminBrief['timeHorizon'],
                  )
                }
              />
            </div>

            <TagsInput
              label="Primary Entities"
              value={brief.primaryEntities}
              onChange={next => update('primaryEntities', next)}
              placeholder="Add entity and press Enter"
            />

            <TagsInput
              label="Tags"
              value={brief.tags}
              onChange={next => update('tags', next)}
              placeholder="Add tag and press Enter"
            />
          </div>

          <div className="space-y-4">
            <Textarea
              label="Executive Summary (Public)"
              value={brief.executiveSummary}
              onChange={e => update('executiveSummary', e.target.value)}
              placeholder="Public-facing summary…"
              rows={6}
            />

            <Textarea
              label="Key Intelligence (Subscribers Only)"
              value={brief.keyIntelligence}
              onChange={e => update('keyIntelligence', e.target.value)}
              placeholder="Detailed intelligence content…"
              rows={6}
            />

            <Textarea
              label="Risk Assessment (Subscribers Only)"
              value={brief.riskAssessment}
              onChange={e => update('riskAssessment', e.target.value)}
              placeholder="Detailed risk assessment…"
              rows={6}
            />
          </div>
        </div>

        <div className="border-border mt-6 flex justify-end gap-2 border-t pt-4">
          <Link
            href={returnHref}
            className="text-muted hover:text-foreground inline-flex h-9 items-center px-4 text-sm font-medium"
          >
            Cancel
          </Link>
        </div>
      </div>
    </form>
  );
};
