import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

export type DataTableColumn<T> = {
  /** Stable key used to identify the column. */
  id: string;
  /** Column header label / node. */
  header: ReactNode;
  /** Renders the cell content for a row. */
  cell: (row: T) => ReactNode;
  /** Tailwind classes applied to both the `<th>` and `<td>` for layout. */
  className?: string;
  /** Override classes for the header cell only. */
  headerClassName?: string;
  /** Override classes for the body cell only. */
  cellClassName?: string;
};

export type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  emptyMessage?: string;
  className?: string;
};

/**
 * Lightweight generic table used by admin list pages. Each column declares
 * its own renderer so callers can compose badges, action buttons, etc.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  emptyMessage = 'No items to show.',
  className,
}: DataTableProps<T>) {
  return (
    <div
      className={cn(
        'border-border bg-background-alt overflow-hidden rounded-lg border',
        className,
      )}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-left">
          <thead className="border-border bg-surface/40 border-b">
            <tr>
              {columns.map(col => (
                <th
                  key={col.id}
                  scope="col"
                  className={cn(
                    'text-muted px-4 py-3 text-xs font-semibold tracking-wider uppercase',
                    col.className,
                    col.headerClassName,
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="text-muted px-4 py-10 text-center text-sm"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map(row => (
                <tr
                  key={rowKey(row)}
                  className="border-border-subtle hover:bg-surface/30 border-b transition-colors last:border-b-0"
                >
                  {columns.map(col => (
                    <td
                      key={col.id}
                      className={cn(
                        'text-body px-4 py-4 align-middle text-sm',
                        col.className,
                        col.cellClassName,
                      )}
                    >
                      {col.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
