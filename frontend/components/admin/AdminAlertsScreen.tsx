'use client';

import {
  Button,
  DataTable,
  type DataTableColumn,
  ErrorState,
  LoadingState,
  Modal,
  PageHeader,
  ScoreBadge,
  StatusTag,
} from '@/components';
import { HoverTip } from '@/components/ui/HoverTip';
import {
  ADMIN_ALERT_CATEGORY_OPTIONS,
  ADMIN_ALERT_STATUS_OPTIONS,
  ADMIN_RISK_LEVEL_OPTIONS,
} from '@/data/adminFilterOptions';
import {
  ADMIN_ALERTS_PAGE_SIZE,
  useAdminAlertReviewMutation,
  useAdminAlertsListQuery,
  useDebouncedValue,
} from '@/hooks';
import { getApiErrorMessage } from '@/lib/api/queryError';
import { formatAdminDate } from '@/lib/formatAdminDate';
import { cn } from '@/lib/utils';
import type { AdminAlert } from '@/types/admin';
import { Ban, Check } from 'lucide-react';
import Link from 'next/link';
import { type FC, type ReactNode, useState } from 'react';
import { toast } from 'sonner';

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

type AlertReviewAction = 'approved' | 'false_positive';

type PendingAlertReview = {
  alert: AdminAlert;
  action: AlertReviewAction;
};

const iconButtonClass =
  'text-muted hover:bg-surface inline-flex size-8 cursor-pointer items-center justify-center rounded-md transition-colors disabled:pointer-events-none disabled:opacity-40';

function ReviewIconButton({
  label,
  disabled,
  tone,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  tone: 'success' | 'danger';
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <HoverTip
      label={label}
      bubbleClassName="bottom-auto left-auto right-full top-1/2 mb-0 mr-1.5 translate-x-0 -translate-y-1/2"
    >
      <button
        type="button"
        disabled={disabled}
        aria-label={label}
        onClick={onClick}
        className={cn(
          iconButtonClass,
          tone === 'success' && 'hover:text-success',
          tone === 'danger' && 'hover:text-danger',
        )}
      >
        {children}
      </button>
    </HoverTip>
  );
}

function buildAlertColumns({
  reviewDisabled,
  onReview,
}: {
  reviewDisabled: boolean;
  onReview: (alert: AdminAlert, action: AlertReviewAction) => void;
}): DataTableColumn<AdminAlert>[] {
  return [
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
      cell: row => (
        <ScoreBadge
          score={row.riskScore}
          riskLevel={row.riskLevel}
          riskBand={row.riskBand}
        />
      ),
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
      cell: row =>
        row.status === 'published' ? (
          <span className="text-muted text-sm">—</span>
        ) : (
          <div className="flex items-center gap-1">
            <ReviewIconButton
              label="Approve"
              disabled={reviewDisabled}
              tone="success"
              onClick={() => onReview(row, 'approved')}
            >
              <Check className="size-4" strokeWidth={2} aria-hidden />
            </ReviewIconButton>
            <ReviewIconButton
              label="False Positive"
              disabled={reviewDisabled}
              tone="danger"
              onClick={() => onReview(row, 'false_positive')}
            >
              <Ban className="size-4" strokeWidth={2} aria-hidden />
            </ReviewIconButton>
          </div>
        ),
      className: 'w-[100px]',
    },
  ];
}

const SEARCH_DEBOUNCE_MS = 400;

export const AdminAlertsScreen: FC = () => {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string>('all');
  const [risk, setRisk] = useState<string>('all');
  const [status, setStatus] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [pendingReview, setPendingReview] = useState<PendingAlertReview | null>(
    null,
  );
  const debouncedSearch = useDebouncedValue(search, SEARCH_DEBOUNCE_MS);
  const reviewMutation = useAdminAlertReviewMutation();

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
  const isReviewPending = reviewMutation.isPending;

  const columns = buildAlertColumns({
    reviewDisabled: isReviewPending,
    onReview: (alert, action) => setPendingReview({ alert, action }),
  });

  async function confirmPendingReview() {
    if (!pendingReview || isReviewPending) return;

    const { alert, action } = pendingReview;

    try {
      await reviewMutation.mutateAsync({
        alertId: alert.id,
        payload: { review_status: action },
      });
      toast.success(
        action === 'approved'
          ? 'Alert approved and published.'
          : 'Alert marked as false positive and excluded.',
      );
      setPendingReview(null);
    } catch (reviewError) {
      toast.error(
        getApiErrorMessage(reviewError, 'Unable to submit review. Please try again.'),
      );
    }
  }

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
            options: ADMIN_ALERT_CATEGORY_OPTIONS,
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

      <Modal
        open={pendingReview !== null}
        onClose={() => {
          if (isReviewPending) return;
          setPendingReview(null);
        }}
        labelledBy="alert-review-confirm-title"
        className="max-w-md p-6"
      >
        {pendingReview ? (
          <>
            <h2
              id="alert-review-confirm-title"
              className="font-heading text-foreground text-lg font-semibold tracking-tight"
            >
              {pendingReview.action === 'approved'
                ? 'Publish this alert?'
                : 'Mark as false positive?'}
            </h2>
            <p className="text-muted mt-2 text-sm leading-relaxed">
              {pendingReview.action === 'approved'
                ? 'It will appear in the subscriber feed. Open the alert if you need to edit the summary or risk level first.'
                : 'It will be excluded from subscriber feeds.'}
            </p>
            <p className="text-foreground mt-3 text-sm font-medium">
              {pendingReview.alert.title}
            </p>
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                size="md"
                variant="outline"
                disabled={isReviewPending}
                onClick={() => setPendingReview(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="md"
                variant={
                  pendingReview.action === 'approved' ? 'default' : 'danger'
                }
                loading={isReviewPending}
                onClick={() => void confirmPendingReview()}
              >
                {pendingReview.action === 'approved'
                  ? 'Approve'
                  : 'Mark False Positive'}
              </Button>
            </div>
          </>
        ) : null}
      </Modal>
    </div>
  );
};
