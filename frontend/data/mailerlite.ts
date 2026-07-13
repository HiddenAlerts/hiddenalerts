/**
 * MailerLite newsletter embed config.
 *
 * Trust boundary: only Official MailerLite CDN + numeric account / alphanumeric form ids.
 * Do not load scripts from any other host.
 */

/** Official MailerLite universal JS (https only). */
export const MAILERLITE_UNIVERSAL_SCRIPT_URL =
  'https://assets.mailerlite.com/js/universal.js' as const;

/** Allowed script origin — reject anything else. */
export const MAILERLITE_ALLOWED_SCRIPT_ORIGIN =
  'https://assets.mailerlite.com' as const;

/** HiddenAlerts MailerLite account (digits only). */
export const MAILERLITE_ACCOUNT_ID = '2500813' as const;

/** Embedded form id (`data-form`) — HiddenAlerts Intelligence group. */
export const MAILERLITE_EMBED_FORM_ID = 'AIKp4K' as const;

/** In-page anchors that scroll to a MailerLite signup embed. */
export const MAILERLITE_PRICING_ANCHOR = '#newsletter-signup';
export const MAILERLITE_FOOTER_ANCHOR = '#newsletter';

/** Account ids are numeric — refuse anything else before calling `ml()`. */
export function isSafeMailerLiteAccountId(id: string): boolean {
  return /^\d{1,12}$/.test(id);
}

/** Form ids from MailerLite are alphanumeric — refuse anything else for `data-form`. */
export function isSafeMailerLiteFormId(id: string): boolean {
  return /^[A-Za-z0-9]{1,32}$/.test(id);
}

/** Only the official CDN URL may be used for the universal script. */
export function isAllowedMailerLiteScriptUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return (
      parsed.protocol === 'https:' &&
      parsed.origin === MAILERLITE_ALLOWED_SCRIPT_ORIGIN &&
      parsed.pathname === '/js/universal.js'
    );
  } catch {
    return false;
  }
}
