import type { HttpRequestError } from './client';

/** Status codes with a clearer message than the generic "(status) Request failed" text. */
const STATUS_MESSAGES: Record<number, string> = {
  413: 'That request is too large for the server to accept. Try a smaller file.',
  401: 'Your session has expired. Please sign in again.',
  403: "You don't have permission to do that.",
};

/** Turns a thrown fetch/query error into a user-facing message. */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const e = error as HttpRequestError;
    if (typeof e.status === 'number') {
      return STATUS_MESSAGES[e.status] ?? `The server returned an error (${e.status}). ${e.message}`;
    }
    return error.message;
  }
  return fallback;
}
