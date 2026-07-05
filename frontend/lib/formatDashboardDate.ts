/** Long-form timestamp for dashboard alert rows, e.g. `May 25, 2026, 3:00 PM UTC`. */
export function formatDashboardAlertTimestampUtc(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';

  const datePart = d.toLocaleString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const timePart = d.toLocaleString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC',
  });

  return `${datePart}, ${timePart} UTC`;
}

/** Date line only, e.g. `May 25, 2026` (UTC). */
export function formatDashboardAlertDateOnlyUtc(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/** Time line with UTC suffix, e.g. `3:00 PM UTC`. */
export function formatDashboardAlertTimeUtcLine(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const timePart = d.toLocaleString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC',
  });
  return `${timePart} UTC`;
}

/** Compact footer line for top-alert cards, e.g. `May 28, 2026 • 9:15 AM UTC`. */
export function formatTopAlertFooterTimestampUtc(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';

  const datePart = d.toLocaleString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const timePart = d.toLocaleString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC',
  });

  return `${datePart} • ${timePart} UTC`;
}

/**
 * Relative time label for the dashboard “Updated …” status line, e.g.
 * `just now`, `5 minutes ago`, `2 hours ago`, `3 days ago`. Falls back to the
 * absolute UTC timestamp once the gap exceeds a month.
 */
export function formatDashboardUpdatedRelative(iso: string, now: Date = new Date()) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';

  const deltaMs = Math.max(0, now.getTime() - d.getTime());
  const seconds = Math.floor(deltaMs / 1000);
  if (seconds < 45) return 'just now';

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`;

  return formatDashboardLastUpdatedUtc(iso);
}

/** Dashboard header “last updated” line. */
export function formatDashboardLastUpdatedUtc(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';

  return d.toLocaleString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC',
    timeZoneName: 'short',
  });
}
