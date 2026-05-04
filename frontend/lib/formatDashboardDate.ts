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
