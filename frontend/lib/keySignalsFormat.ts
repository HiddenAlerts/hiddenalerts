/**
 * The Key Signals field keeps its rich-text editor in the UI, but the API's
 * `key_signals` is a plain string array (one entry per signal). These convert
 * between the two at the API boundary only — nothing else needs to know.
 */

/** Rich-text HTML -> one string per list item/paragraph, in document order. */
export function keySignalsHtmlToArray(html: string): string[] {
  if (!html.trim()) return [];
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return Array.from(doc.body.querySelectorAll('li, p'))
    .map(el => el.textContent?.trim() ?? '')
    .filter(Boolean);
}

/** String array -> a bullet list HTML string the rich text editor can display. */
export function keySignalsArrayToHtml(signals: string[]): string {
  const items = signals.map(s => s.trim()).filter(Boolean);
  if (items.length === 0) return '';
  return `<ul>${items.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>`;
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
