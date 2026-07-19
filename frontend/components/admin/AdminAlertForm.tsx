'use client';

import {
  Button,
  Input,
  PageHeader,
  Select,
  type SelectOption,
  TagsInput,
  Textarea,
} from '@/components';
import { ADMIN_ALERT_CATEGORY_FORM_OPTIONS } from '@/data/adminFilterOptions';
import { ADMIN_MOCK_BRIEFS } from '@/data/adminMockBriefs';
import type { AdminAlert } from '@/types/admin';
import { Feather } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { type FC, type FormEvent, useMemo, useState } from 'react';

const SUMMARY_MAX_LENGTH = 300;

const EMPTY_ALERT: AdminAlert = {
  id: '',
  title: '',
  riskScore: 0,
  category: ADMIN_ALERT_CATEGORY_FORM_OPTIONS[0].value,
  date: new Date().toISOString().slice(0, 10),
  summary: '',
  briefId: undefined,
  tags: [],
  status: 'draft',
};

export type AdminAlertFormProps = {
  initial?: AdminAlert;
  title?: string;
  subtitle?: string;
  returnHref?: string;
};

export const AdminAlertForm: FC<AdminAlertFormProps> = ({
  initial,
  title = 'Create / Edit Alert',
  subtitle = 'Add or update alert',
  returnHref = '/admin/alerts',
}) => {
  const router = useRouter();
  const [alert, setAlert] = useState<AdminAlert>(initial ?? EMPTY_ALERT);

  const briefOptions = useMemo<SelectOption[]>(
    () => [
      { value: '', label: '— None —' },
      ...ADMIN_MOCK_BRIEFS.map(b => ({ value: b.id, label: b.title })),
    ],
    [],
  );

  const update = <K extends keyof AdminAlert>(key: K, value: AdminAlert[K]) =>
    setAlert(prev => ({ ...prev, [key]: value }));

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
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
              onClick={() => router.push(returnHref)}
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

      <div className="border-border bg-background-alt rounded-lg border p-4 sm:p-6">
        <div className="space-y-4">
          <Input
            label="Title"
            required
            addAsterisk
            value={alert.title}
            onChange={e => update('title', e.target.value)}
            placeholder="Alert title"
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Risk Score"
              required
              addAsterisk
              type="number"
              min={0}
              max={100}
              value={String(alert.riskScore)}
              onChange={e => update('riskScore', Number(e.target.value) || 0)}
            />
            <Select
              label="Category"
              required
              addAsterisk
              options={ADMIN_ALERT_CATEGORY_FORM_OPTIONS}
              value={alert.category}
              onChange={e => update('category', e.target.value)}
            />
          </div>

          <Input
            label="Date"
            required
            addAsterisk
            type="date"
            value={alert.date}
            onChange={e => update('date', e.target.value)}
          />

          <Textarea
            label="Summary"
            required
            addAsterisk
            value={alert.summary}
            onChange={e => update('summary', e.target.value)}
            placeholder="Short alert summary…"
            maxLength={SUMMARY_MAX_LENGTH}
            showCounter
            rows={5}
          />

          <Select
            label="Link to Brief (optional)"
            options={briefOptions}
            value={alert.briefId ?? ''}
            onChange={e =>
              update('briefId', e.target.value === '' ? undefined : e.target.value)
            }
          />

          <TagsInput
            label="Tags"
            value={alert.tags}
            onChange={next => update('tags', next)}
            placeholder="Add tag and press Enter"
          />
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
