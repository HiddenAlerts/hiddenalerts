/**
 * Where Supabase should send users after email confirmation (and similar
 * auth links). Uses `NEXT_PUBLIC_APP_URL` when set so production emails do
 * not fall back to the Supabase dashboard Site URL (often localhost).
 */
export function getAppOrigin(): string {
  const fromEnv = process.env.NEXT_PUBLIC_APP_URL?.trim().replace(/\/$/, '');
  if (fromEnv) return fromEnv;
  if (typeof window !== 'undefined') return window.location.origin;
  return '';
}

/** Full URL for `signUp({ options: { emailRedirectTo } })`. */
export function getEmailConfirmRedirectUrl(
  path: string = '/email-confirmed',
): string {
  const origin = getAppOrigin();
  const segment = path.startsWith('/') ? path : `/${path}`;
  return origin ? `${origin}${segment}` : segment;
}
