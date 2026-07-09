'use client';

import {
  Button,
  DataTable,
  type DataTableColumn,
  ErrorState,
  LoadingState,
  PageHeader,
  ScoreBadge,
  StatusTag,
} from '@/components';
import {
  ADMIN_CATEGORY_OPTIONS,
  ADMIN_RISK_LEVEL_OPTIONS,
  ADMIN_STATUS_OPTIONS,
} from '@/data/adminFilterOptions';
import { ADMIN_BRIEFS_PAGE_SIZE, useAdminBriefsListQuery } from '@/hooks';
import { getApiErrorMessage } from '@/lib/api/queryError';
import { formatAdminDate } from '@/lib/formatAdminDate';
import type { AdminBriefListItem, AdminPublishStatus } from '@/types/admin';
import { Plus } from 'lucide-react';
import Link from 'next/link';
import { type FC, useState } from 'react';

import { AdminPagination } from './AdminPagination';
import { AdminRowActions } from './AdminRowActions';
import { AdminTableToolbar } from './AdminTableToolbar';

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

const columns: DataTableColumn<AdminBriefListItem>[] = [
  {
    id: 'title',
    header: 'Title',
    cell: row => (
      <Link
        href={`/admin/briefs/${row.id}`}
        className="text-foreground hover:text-primary-400 line-clamp-2 font-medium"
      >
        {row.title}
      </Link>
    ),
    className: 'min-w-[260px] max-w-[360px]',
  },
  {
    id: 'riskScore',
    header: 'Risk Score',
    cell: row => <ScoreBadge score={row.riskScore} />,
    className: 'w-[120px]',
  },
  {
    id: 'category',
    header: 'Category',
    cell: row => <span className="text-body">{row.category}</span>,
    className: 'w-[160px]',
  },
  {
    id: 'date',
    header: 'Date',
    cell: row => (
      <span className="text-muted tabular-nums">
        {formatAdminDate(row.publishedDate ?? row.createdAt)}
      </span>
    ),
    className: 'w-[140px]',
  },
  {
    id: 'status',
    header: 'Status',
    cell: row => (
      <StatusTag tone={STATUS_TONE[row.status]}>
        {STATUS_LABEL[row.status]}
      </StatusTag>
    ),
    className: 'w-[120px]',
  },
  {
    id: 'actions',
    header: 'Actions',
    cell: row => <AdminRowActions editHref={`/admin/briefs/${row.id}/edit`} />,
    className: 'w-[100px]',
  },
];

export const AdminBriefsScreen: FC = () => {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('all');
  const [risk, setRisk] = useState<string>('all');
  const [category, setCategory] = useState<string>('all');
  const [page, setPage] = useState(1);

  const resetPage = () => setPage(1);

  const { data, isPending, isError, error, refetch } = useAdminBriefsListQuery({
    page,
    status,
    risk,
    category,
    search,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Briefs"
        subtitle="Manage intelligence briefs"
        actions={
          <Link href="/admin/briefs/new">
            <Button
              type="button"
              size="sm"
              leftIcon={<Plus className="size-4" aria-hidden />}
            >
              New Brief
            </Button>
          </Link>
        }
      />

      <AdminTableToolbar
        searchValue={search}
        onSearchChange={value => {
          setSearch(value);
          resetPage();
        }}
        searchPlaceholder="Search briefs..."
        filters={[
          {
            id: 'briefs-status',
            value: status,
            ariaLabel: 'Filter by status',
            options: ADMIN_STATUS_OPTIONS,
            onChange: value => {
              setStatus(value);
              resetPage();
            },
          },
          {
            id: 'briefs-risk',
            value: risk,
            ariaLabel: 'Filter by risk level',
            options: ADMIN_RISK_LEVEL_OPTIONS,
            onChange: value => {
              setRisk(value);
              resetPage();
            },
          },
          {
            id: 'briefs-category',
            value: category,
            ariaLabel: 'Filter by category',
            options: ADMIN_CATEGORY_OPTIONS,
            onChange: value => {
              setCategory(value);
              resetPage();
            },
          },
        ]}
      />

      {isError ? (
        <ErrorState
          message={getApiErrorMessage(error, 'Unable to load briefs. Please try again.')}
          onRetry={() => void refetch()}
        />
      ) : isPending ? (
        <LoadingState label="Loading briefs…" />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            rowKey={row => row.id}
            emptyMessage="No briefs match your filters."
          />

          <AdminPagination
            page={page}
            pageSize={ADMIN_BRIEFS_PAGE_SIZE}
            totalItems={data?.total ?? 0}
            itemLabel="briefs"
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
};
