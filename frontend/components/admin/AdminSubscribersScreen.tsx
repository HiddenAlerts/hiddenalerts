'use client';

import {
  Button,
  DataTable,
  type DataTableColumn,
  PageHeader,
} from '@/components';
import { ADMIN_MOCK_SUBSCRIBERS } from '@/data/adminMockSubscribers';
import { formatAdminDateTime } from '@/lib/formatAdminDate';
import type { AdminSubscriber } from '@/types/admin';
import { Download } from 'lucide-react';
import { type FC, useMemo, useState } from 'react';

import { AdminPagination } from './AdminPagination';
import { AdminTableToolbar } from './AdminTableToolbar';

const PAGE_SIZE = 5;

const columns: DataTableColumn<AdminSubscriber>[] = [
  {
    id: 'email',
    header: 'Email',
    cell: row => <span className="text-foreground font-medium">{row.email}</span>,
    className: 'min-w-[260px]',
  },
  {
    id: 'joinedAt',
    header: 'Date Joined',
    cell: row => (
      <span className="text-muted tabular-nums">
        {formatAdminDateTime(row.joinedAt)}
      </span>
    ),
    className: 'w-[220px]',
  },
];

export const AdminSubscribersScreen: FC = () => {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return ADMIN_MOCK_SUBSCRIBERS;
    return ADMIN_MOCK_SUBSCRIBERS.filter(sub =>
      sub.email.toLowerCase().includes(term),
    );
  }, [search]);

  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const rows = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, currentPage]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Subscribers"
        subtitle="View email subscribers"
        actions={
          <Button
            type="button"
            size="sm"
            variant="outline"
            leftIcon={<Download className="size-4" aria-hidden />}
          >
            Export
          </Button>
        }
      />

      <AdminTableToolbar
        searchValue={search}
        onSearchChange={value => {
          setSearch(value);
          setPage(1);
        }}
        searchPlaceholder="Search subscribers..."
      />

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={row => row.id}
        emptyMessage="No subscribers match your search."
      />

      <AdminPagination
        page={currentPage}
        pageSize={PAGE_SIZE}
        totalItems={total}
        itemLabel="subscribers"
        onPageChange={setPage}
      />
    </div>
  );
};
