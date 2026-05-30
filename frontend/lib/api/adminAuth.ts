import type {
  AdminChangePasswordRequest,
  AdminLoginRequest,
  AdminLoginResponse,
  AdminUser,
} from '@/types/auth';

import { apiGet, apiPost } from './client';

/** `POST /api/v1/auth/login` — exchanges email + password for a backend JWT. */
export function loginAdmin(body: AdminLoginRequest) {
  return apiPost<AdminLoginResponse>('/v1/auth/login', body);
}

/** `GET /api/v1/auth/me` — returns the current admin profile. */
export function fetchAdminMe(token: string) {
  return apiGet<AdminUser>('/v1/auth/me', { token });
}

/** `POST /api/v1/auth/change-password` — changes the admin password. */
export function changeAdminPassword(
  token: string,
  body: AdminChangePasswordRequest,
) {
  return apiPost<AdminUser>('/v1/auth/change-password', body, { token });
}
