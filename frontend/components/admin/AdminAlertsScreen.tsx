'use client';

import {
  Button,
  DataTable,
  type DataTableColumn,
  PageHeader,
  ScoreBadge,
  StatusTag,
} from '@/components';
import {
  ADMIN_CATEGORY_OPTIONS,
  ADMIN_RISK_LEVEL_OPTIONS,
  ADMIN_STATUS_OPTIONS,
  riskScoreToLevel,
} from '@/data/adminFilterOptions';
import { ADMIN_MOCK_ALERTS } from '@/data/adminMockAlerts';
import { formatAdminDate } from '@/lib/formatAdminDate';
import type { AdminAlert } from '@/types/admin';
import { Plus } from 'lucide-react';
import Link from 'next/link';
import { type FC, useMemo, useState } from 'react';

import { AdminPagination } from './AdminPagination';
import { AdminRowActions } from './AdminRowActions';
import { AdminTableToolbar } from './AdminTableToolbar';

const PAGE_SIZE = 5;

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
  {
    id: 'actions',
    header: 'Actions',
    cell: row => <AdminRowActions editHref={`/admin/alerts/${row.id}/edit`} />,
    className: 'w-[100px]',
  },
];

export const AdminAlertsScreen: FC = () => {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string>('all');
  const [risk, setRisk] = useState<string>('all');
  const [status, setStatus] = useState<string>('all');
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return ADMIN_MOCK_ALERTS.filter(alert => {
      if (term && !alert.title.toLowerCase().includes(term)) return false;
      if (category !== 'all' && alert.category !== category) return false;
      if (risk !== 'all' && riskScoreToLevel(alert.riskScore) !== risk)
        return false;
      if (status !== 'all' && alert.status !== status) return false;
      return true;
    });
  }, [search, category, risk, status]);

  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const rows = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, currentPage]);

  const resetPage = () => setPage(1);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alerts"
        subtitle="Manage real-time alerts"
        actions={
          <Link href="/admin/alerts/new">
            <Button
              type="button"
              size="sm"
              leftIcon={<Plus className="size-4" aria-hidden />}
            >
              New Alert
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
            options: ADMIN_STATUS_OPTIONS,
            onChange: value => {
              setStatus(value);
              resetPage();
            },
          },
        ]}
      />

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={row => row.id}
        emptyMessage="No alerts match your filters."
      />

      <AdminPagination
        page={currentPage}
        pageSize={PAGE_SIZE}
        totalItems={total}
        itemLabel="alerts"
        onPageChange={setPage}
      />
    </div>
  );
};
