import type { HttpRequestError } from './client';

/** Status codes with a clearer message than the generic "(status) Request failed" text. */
const STATUS_MESSAGES: Record<number, string> = {
  413: 'That request is too large for the server to accept. Try a smaller file.',
  401: 'Your session has expired. Please sign in again.',
  403: "You don't have permission to do that.",
  409:
    'This conflicts with an existing brief — often a duplicate title or slug. Change the title slightly, or open the existing draft from the briefs list.',
};

/** Pulls FastAPI-style `detail` (string or validation array) from an error body. */
function extractApiDetail(body: unknown): string | undefined {
  if (!body || typeof body !== 'object') return undefined;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) return detail.trim();
  if (Array.isArray(detail) && detail.length > 0) {
    const parts = detail
      .map(item => {
        if (!item || typeof item !== 'object') return null;
        const msg = (item as { msg?: unknown }).msg;
        return typeof msg === 'string' ? msg : null;
      })
      .filter((msg): msg is string => Boolean(msg));
    if (parts.length > 0) return parts.join(' ');
  }
  return undefined;
}

/** Turns a thrown fetch/query error into a user-facing message. */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const e = error as HttpRequestError;
    if (typeof e.status === 'number') {
      const detail = extractApiDetail(e.body);
      if (detail) {
        // Prefer a readable backend detail; keep conflict context for 409.
        if (e.status === 409) {
          return `${STATUS_MESSAGES[409]} (${detail})`;
        }
        return detail;
      }
      return STATUS_MESSAGES[e.status] ?? `The server returned an error (${e.status}). ${e.message}`;
    }

    // Browser `fetch` network failures (CORS, offline, wrong API host, aborted):
    // message is typically "Failed to fetch" with no HTTP status.
    const msg = error.message.trim();
    if (/failed to fetch|networkerror|load failed|network request failed/i.test(msg)) {
      return (
        'Could not reach the server (network error). Check your connection, ' +
        'confirm you are still signed in, and try again. If this keeps happening, ' +
        'ask your developer to check the API URL / CORS settings.'
      );
    }
    return msg || fallback;
  }
  return fallback;
}
