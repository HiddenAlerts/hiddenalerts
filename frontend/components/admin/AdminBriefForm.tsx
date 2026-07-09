'use client';

import {
  Button,
  ImageUpload,
  Input,
  Modal,
  PageHeader,
  RichTextEditor,
  Select,
  StatusTag,
  SupportingAlertsInput,
  Switch,
  TagsInput,
} from '@/components';
import { BriefReader } from '@/components/briefs';
import {
  ADMIN_CATEGORY_FORM_OPTIONS,
  ADMIN_CONFIDENCE_LEVEL_OPTIONS,
  ADMIN_RISK_LEVEL_FORM_OPTIONS,
  ADMIN_TIME_HORIZON_OPTIONS,
} from '@/data/adminFilterOptions';
import {
  useArchiveAdminBriefMutation,
  usePublishAdminBriefMutation,
  useSaveAdminBriefMutation,
  useSetAdminBriefFeaturedMutation,
} from '@/hooks';
import { getApiErrorMessage } from '@/lib/api/queryError';
import { adminBriefToDetail } from '@/lib/briefDetail';
import { slugify } from '@/lib/utils';
import type { AdminBrief, AdminPublishStatus } from '@/types/admin';
import { Archive, Eye, Feather, FileEdit } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  type FC,
  type FormEvent,
  useEffect,
  useRef,
  useState,
} from 'react';
import { toast } from 'sonner';

const MAX_IMAGE_BYTES = 2 * 1024 * 1024;

const EMPTY_BRIEF: AdminBrief = {
  id: '',
  briefCode: '',
  title: '',
  slug: '',
  category: ADMIN_CATEGORY_FORM_OPTIONS[0].value,
  riskScore: 0,
  riskLevel: 'low',
  timeHorizon: 'immediate',
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
  analystNotes: '',
  confidenceLevel: 'medium',
  supportingAlerts: [],
  featured: false,
  isPremium: false,
  status: 'draft',
  alertsCount: 0,
  readTimeMinutes: 0,
  createdAt: '',
  updatedAt: '',
};

export type AdminBriefFormProps = {
  /** Pre-fills the form for the edit flow. */
  initial?: AdminBrief;
  /** Header title (defaults vary by mode). */
  title?: string;
  /** Header subtitle. */
  subtitle?: string;
  /** Where to navigate when the user saves/publishes/archives/cancels. */
  returnHref?: string;
};

const SECTION_CLASSNAME =
  'border-border bg-background-alt space-y-5 rounded-lg border p-4 sm:p-6';

const SECTION_HEADING_CLASSNAME =
  'font-heading text-foreground text-sm font-semibold tracking-wide uppercase';

const STATUS_TONE: Record<AdminPublishStatus, 'success' | 'neutral' | 'warning'> = {
  published: 'success',
  draft: 'neutral',
  archived: 'warning',
};

const STATUS_LABEL: Record<AdminPublishStatus, string> = {
  published: 'Published',
  draft: 'Draft',
  archived: 'Archived',
};

/**
 * Shared form for both creating and editing a brief, wired to the real
 * admin API. Status only changes via the dedicated Publish/Archive actions
 * (the backend has no editable `status` field), and Featured only changes
 * via its own feature/unfeature call once the brief has been saved.
 */
export const AdminBriefForm: FC<AdminBriefFormProps> = ({
  initial,
  title = 'Create / Edit Intelligence Brief',
  subtitle = 'All fields marked with * are required.',
  returnHref = '/admin/briefs',
}) => {
  const router = useRouter();
  const [brief, setBrief] = useState<AdminBrief>(initial ?? EMPTY_BRIEF);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<
    'draft' | 'publish' | 'archive' | null
  >(null);

  const [imageFile, setImageFile] = useState<File | undefined>();
  const [imagePreview, setImagePreview] = useState<string | undefined>(
    initial?.featuredImage,
  );
  const [removeImage, setRemoveImage] = useState(false);
  const localPreviewUrlRef = useRef<string | undefined>(undefined);

  useEffect(
    () => () => {
      if (localPreviewUrlRef.current) URL.revokeObjectURL(localPreviewUrlRef.current);
    },
    [],
  );

  const saveMutation = useSaveAdminBriefMutation();
  const publishMutation = usePublishAdminBriefMutation();
  const archiveMutation = useArchiveAdminBriefMutation();
  const featureMutation = useSetAdminBriefFeaturedMutation();

  const update = <K extends keyof AdminBrief>(key: K, value: AdminBrief[K]) =>
    setBrief(prev => ({ ...prev, [key]: value }));

  function handleTitleChange(nextTitle: string) {
    setBrief(prev => ({ ...prev, title: nextTitle, slug: slugify(nextTitle) }));
  }

  function handleImageSelect(file: File) {
    if (file.size > MAX_IMAGE_BYTES) {
      toast.error('That image is too large — please choose a file under 2MB.');
      return;
    }
    if (localPreviewUrlRef.current) URL.revokeObjectURL(localPreviewUrlRef.current);
    const url = URL.createObjectURL(file);
    localPreviewUrlRef.current = url;
    setImageFile(file);
    setImagePreview(url);
    setRemoveImage(false);
  }

  function handleImageRemove() {
    if (localPreviewUrlRef.current) URL.revokeObjectURL(localPreviewUrlRef.current);
    localPreviewUrlRef.current = undefined;
    setImageFile(undefined);
    setImagePreview(undefined);
    setRemoveImage(true);
  }

  /** Create-or-update, then upload/remove the image if it changed. Returns the saved brief on success. */
  async function persist(): Promise<AdminBrief | undefined> {
    try {
      const saved = await saveMutation.mutateAsync({
        brief,
        imageFile,
        removeImage,
      });
      setBrief(saved);
      setImagePreview(saved.featuredImage);
      setImageFile(undefined);
      setRemoveImage(false);
      return saved;
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Could not save the brief.'));
      return undefined;
    }
  }

  async function handleSave() {
    setPendingAction('draft');
    const saved = await persist();
    setPendingAction(null);
    if (saved) {
      toast.success(saved.status === 'published' ? 'Changes saved.' : 'Draft saved.');
      router.push(returnHref);
    }
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPendingAction('publish');
    const saved = await persist();
    if (saved) {
      try {
        await publishMutation.mutateAsync(saved.id);
        toast.success('Brief published.');
        router.push(returnHref);
      } catch (err) {
        toast.error(getApiErrorMessage(err, 'Could not publish the brief.'));
      }
    }
    setPendingAction(null);
  }

  async function handleArchive() {
    if (!brief.id) return;
    setPendingAction('archive');
    try {
      await archiveMutation.mutateAsync(brief.id);
      toast.success('Brief archived.');
      router.push(returnHref);
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Could not archive the brief.'));
    }
    setPendingAction(null);
  }

  function handleFeaturedToggle(next: boolean) {
    if (!brief.id) return;
    featureMutation.mutate(
      { briefId: brief.id, featured: next },
      {
        onSuccess: saved => {
          setBrief(prev => ({ ...prev, featured: saved.featured }));
          toast.success(next ? 'Marked as featured.' : 'Removed from featured.');
        },
        onError: err =>
          toast.error(getApiErrorMessage(err, 'Could not update featured state.')),
      },
    );
  }

  const canArchive = Boolean(brief.id) && brief.status !== 'archived';
  const canPublish = brief.status !== 'published';
  const saveLabel = brief.status === 'published' ? 'Save Changes' : 'Save Draft';

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
              <StatusTag tone={STATUS_TONE[brief.status]}>
                {STATUS_LABEL[brief.status]}
              </StatusTag>
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              loading={pendingAction === 'draft'}
              disabled={pendingAction !== null}
              onClick={handleSave}
            >
              {saveLabel}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={pendingAction !== null}
              onClick={() => setPreviewOpen(true)}
              leftIcon={<Eye className="size-4" aria-hidden />}
            >
              Preview
            </Button>
            {canArchive ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                loading={pendingAction === 'archive'}
                disabled={pendingAction !== null}
                onClick={handleArchive}
                leftIcon={<Archive className="size-4" aria-hidden />}
              >
                Archive
              </Button>
            ) : null}
            {canPublish ? (
              <Button
                type="submit"
                size="sm"
                loading={pendingAction === 'publish'}
                disabled={pendingAction !== null}
                leftIcon={<Feather className="size-4" aria-hidden />}
              >
                Publish Brief
              </Button>
            ) : null}
          </>
        }
      />

      <Modal open={previewOpen} onClose={() => setPreviewOpen(false)}>
        <BriefReader
          brief={adminBriefToDetail({ ...brief, featuredImage: imagePreview })}
          topBar="preview"
          onClose={() => setPreviewOpen(false)}
        />
      </Modal>

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

        <Select
          label="Time Horizon"
          options={ADMIN_TIME_HORIZON_OPTIONS}
          value={brief.timeHorizon ?? 'immediate'}
          onChange={e =>
            update('timeHorizon', e.target.value as AdminBrief['timeHorizon'])
          }
          parentStyles="sm:max-w-xs"
        />

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
          value={imagePreview}
          onFileSelect={handleImageSelect}
          onRemove={handleImageRemove}
          hint="Recommended size: 1200x675px. Max file size: 2MB."
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
          <RichTextEditor
            label="What Others Miss"
            value={brief.whatOthersMiss}
            onChange={html => update('whatOthersMiss', html)}
            placeholder="Key angles, behaviors or implications overlooked…"
          />
          <RichTextEditor
            label="Implications"
            value={brief.implications}
            onChange={html => update('implications', html)}
            placeholder="Potential impact and consequences…"
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
            <SupportingAlertsInput
              value={brief.supportingAlerts}
              onChange={next => update('supportingAlerts', next)}
            />
            <RichTextEditor
              label="Analyst Notes"
              value={brief.analystNotes}
              onChange={html => update('analystNotes', html)}
              placeholder="Internal notes — never shown to subscribers…"
            />
          </div>

          <div className="space-y-4">
            <div>
              <span className="text-body mb-2 block text-sm font-medium">
                Featured Brief
              </span>
              <Switch
                checked={brief.featured}
                onChange={handleFeaturedToggle}
                disabled={!brief.id || featureMutation.isPending}
                label="Display as the featured brief on the subscriber library"
              />
              <p className="text-muted mt-1.5 text-xs">
                {brief.id
                  ? 'Only one brief can be featured at a time.'
                  : 'Save the brief first to feature it.'}
              </p>
            </div>

            <div>
              <span className="text-body mb-2 block text-sm font-medium">
                Premium Content
              </span>
              <Switch
                checked={brief.isPremium}
                onChange={next => update('isPremium', next)}
                label="Gate this brief behind a premium subscription"
              />
            </div>
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
