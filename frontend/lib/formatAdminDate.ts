/**
 * Formats an ISO date string (or date-only `YYYY-MM-DD`) as `Mon DD, YYYY`,
 * e.g. `May 20, 2026`. Returns `'—'` for invalid input.
 */
export function formatAdminDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date);
}

/**
 * Formats an ISO timestamp as `Mon DD, YYYY HH:MM AM/PM` for table rows that
 * also show the time (e.g. subscribers' joined-at column).
 */
export function formatAdminDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const datePart = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date);
  const timePart = new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC',
  }).format(date);
  return `${datePart} ${timePart}`;
}
