/** Strips HTML tags, returning just the text content (e.g. for card summaries/search indexes). */
export function stripHtmlToText(html: string): string {
  if (!html.trim()) return '';
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return (doc.body.textContent ?? '').trim();
}
