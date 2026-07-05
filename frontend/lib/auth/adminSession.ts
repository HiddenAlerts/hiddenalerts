/**
 * Browser-side helpers for the admin backend JWT.
 *
 * The token is stored in `localStorage` so it survives a tab reload. This is
 * fine for an internal CMS served over HTTPS; if the backend later supports
 * httpOnly cookie auth, swap the storage layer here and nothing else changes.
 */

const STORAGE_KEY = 'hiddenalerts_admin_token';

export function getAdminToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

export function setAdminToken(token: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, token);
}

export function clearAdminToken(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(STORAGE_KEY);
}
