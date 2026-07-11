'use client';

import {
  DataTable,
  type DataTableColumn,
  ErrorState,
  LoadingState,
  PageHeader,
  ScoreBadge,
  StatusTag,
} from '@/components';
import {
  ADMIN_ALERT_STATUS_OPTIONS,
  ADMIN_CATEGORY_OPTIONS,
  ADMIN_RISK_LEVEL_OPTIONS,
} from '@/data/adminFilterOptions';
import {
  ADMIN_ALERTS_PAGE_SIZE,
  useAdminAlertsListQuery,
  useDebouncedValue,
} from '@/hooks';
import { getApiErrorMessage } from '@/lib/api/queryError';
import { formatAdminDate } from '@/lib/formatAdminDate';
import type { AdminAlert } from '@/types/admin';
import Link from 'next/link';
import { type FC, useState } from 'react';

import { AdminPagination } from './AdminPagination';
import { AdminTableToolbar } from './AdminTableToolbar';

const STATUS_TONE = {
  published: 'success',
  draft: 'neutral',
} as const;

const STATUS_LABEL = {
  published: 'Published',
  draft: 'Draft',
} as const;

const columns: DataTableColumn<AdminAlert>[] = [
  {
    id: 'title',
    header: 'Title',
    cell: row => (
      <Link
        href={`/admin/alerts/${row.id}`}
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
      <span className="text-muted tabular-nums">{formatAdminDate(row.date)}</span>
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
];

const SEARCH_DEBOUNCE_MS = 400;

export const AdminAlertsScreen: FC = () => {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string>('all');
  const [risk, setRisk] = useState<string>('all');
  const [status, setStatus] = useState<string>('all');
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebouncedValue(search, SEARCH_DEBOUNCE_MS);

  const resetPage = () => setPage(1);

  const { data, isPending, isFetching, isError, error, refetch } = useAdminAlertsListQuery({
    page,
    status,
    risk,
    category,
    search: debouncedSearch,
  });

  const isInitialLoading = isPending && !data;
  const showFetchingIndicator = isFetching && !isInitialLoading;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alerts"
        subtitle="Manage real-time alerts"
      />

      <AdminTableToolbar
        searchValue={search}
        onSearchChange={value => {
          setSearch(value);
          resetPage();
        }}
        searchPlaceholder="Search alerts..."
        filters={[
          {
            id: 'alerts-category',
            value: category,
            ariaLabel: 'Filter by category',
            options: ADMIN_CATEGORY_OPTIONS,
            onChange: value => {
              setCategory(value);
              resetPage();
            },
          },
          {
            id: 'alerts-risk',
            value: risk,
            ariaLabel: 'Filter by risk level',
            options: ADMIN_RISK_LEVEL_OPTIONS,
            onChange: value => {
              setRisk(value);
              resetPage();
            },
          },
          {
            id: 'alerts-status',
            value: status,
            ariaLabel: 'Filter by status',
            options: ADMIN_ALERT_STATUS_OPTIONS,
            onChange: value => {
              setStatus(value);
              resetPage();
            },
          },
        ]}
      />

      {isError ? (
        <ErrorState
          message={getApiErrorMessage(error, 'Unable to load alerts. Please try again.')}
          onRetry={() => void refetch()}
        />
      ) : isInitialLoading ? (
        <LoadingState label="Loading alerts…" />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            rowKey={row => row.id}
            emptyMessage="No alerts match your filters."
            isLoading={showFetchingIndicator}
            loadingLabel="Updating alerts…"
          />

          <AdminPagination
            page={page}
            pageSize={ADMIN_ALERTS_PAGE_SIZE}
            totalItems={data?.total ?? 0}
            itemLabel="alerts"
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
};
