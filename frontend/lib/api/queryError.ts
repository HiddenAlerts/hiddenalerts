import type { HttpRequestError } from './client';

/** Turns a thrown fetch/query error into a user-facing message. */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const e = error as HttpRequestError;
    if (typeof e.status === 'number') {
      return `The server returned an error (${e.status}). ${e.message}`;
    }
    return error.message;
  }
  return fallback;
}
