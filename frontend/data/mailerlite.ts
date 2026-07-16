/**
 * Newsletter signup anchors.
 *
 * Client: custom HiddenAlerts form → POST /api/newsletter
 * Server: MailerLite API with MAILERLITE_API_TOKEN (email upsert only).
 * No embed script, popup, or MailerLite branding on the landing page.
 */

/** In-page anchors that scroll to the custom newsletter form. */
export const NEWSLETTER_PRICING_ANCHOR = '#newsletter-signup';
export const NEWSLETTER_FOOTER_ANCHOR = '#newsletter';

/** @deprecated Use NEWSLETTER_PRICING_ANCHOR */
export const MAILERLITE_PRICING_ANCHOR = NEWSLETTER_PRICING_ANCHOR;
/** @deprecated Use NEWSLETTER_FOOTER_ANCHOR */
export const MAILERLITE_FOOTER_ANCHOR = NEWSLETTER_FOOTER_ANCHOR;
