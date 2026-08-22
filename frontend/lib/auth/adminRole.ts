import type { AdminUser } from '@/types/auth';

/** Backend Admin authorization requires `user.role === "admin"`. */
export function isAdminRole(user: Pick<AdminUser, 'role'>): boolean {
  return user.role === 'admin';
}

/**
 * Thrown when credentials are valid but the account is not an Admin.
 * Login UI should show a clear access message (not "invalid password").
 */
export class AdminAccessDeniedError extends Error {
  constructor(
    message = 'This account does not have Admin access. Contact a HiddenAlerts administrator if you need access.',
  ) {
    super(message);
    this.name = 'AdminAccessDeniedError';
  }
}

export function isAdminAccessDeniedError(err: unknown): boolean {
  return err instanceof AdminAccessDeniedError ||
    (typeof err === 'object' &&
      err !== null &&
      (err as { name?: string }).name === 'AdminAccessDeniedError');
}
