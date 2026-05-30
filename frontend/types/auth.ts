/**
 * Admin user shape returned by `POST /api/v1/auth/login` and
 * `GET /api/v1/auth/me`.
 */
export type AdminUser = {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
  full_name: string | null;
  wants_high_alert_email?: boolean;
  wants_digest_email?: boolean;
  wants_weekly_report_email?: boolean;
};

export type AdminLoginRequest = {
  email: string;
  password: string;
};

export type AdminLoginResponse = {
  access_token: string;
  token_type: string;
  /** Token lifetime in seconds (currently 30 days = 2592000). */
  expires_in: number;
  user: AdminUser;
};

export type AdminChangePasswordRequest = {
  current_password: string;
  new_password: string;
};
