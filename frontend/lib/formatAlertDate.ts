export function formatAlertDate(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';

  const day = d.getDate();
  const month = d.toLocaleString('en-GB', { month: 'short' });
  const time = d
    .toLocaleString('en-GB', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
    .toLowerCase();

  return `${day} ${month} — ${time}`;
}
