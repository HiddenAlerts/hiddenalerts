export function formatAlertDate(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';

  const day = d.getDate();
  const month = d.toLocaleString('en-GB', { month: 'short' });
  const year = d.getFullYear();
  const time = d
    .toLocaleString('en-GB', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
    .toLowerCase();

  return `${day} ${month} ${year} — ${time}`;
}

/** MVP-friendly published date string (local calendar), e.g. `Mar 22, 2026`. */
export function formatAlertDatePublished(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';

  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function formatRelativeTime(iso: string) {
  const date = new Date(iso);
  const ts = date.getTime();
  if (Number.isNaN(ts)) return '—';

  const diffMs = Date.now() - ts;
  const future = diffMs < 0;
  const absMs = Math.abs(diffMs);

  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  const week = 7 * day;

  if (absMs < minute) return future ? 'in <1m' : 'just now';
  if (absMs < hour) {
    const v = Math.floor(absMs / minute);
    return future ? `in ${v}m` : `${v}m ago`;
  }
  if (absMs < day) {
    const v = Math.floor(absMs / hour);
    return future ? `in ${v}h` : `${v}h ago`;
  }
  if (absMs < week) {
    const v = Math.floor(absMs / day);
    return future ? `in ${v}d` : `${v}d ago`;
  }
  const v = Math.floor(absMs / week);
  return future ? `in ${v}w` : `${v}w ago`;
}
