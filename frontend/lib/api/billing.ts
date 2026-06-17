import type {
  BillingStatusResponse,
  CheckoutRequest,
  CheckoutResponse,
  CustomerPortalResponse,
} from '@/types/billing';

import { apiGet, apiPost } from './client';

/**
 * Returns a UUID for `X-Idempotency-Key`. Per backend spec, generate a fresh
 * key per checkout attempt; reuse only when retrying the *same* request body.
 */
function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  // Fallback for very old runtimes (unlikely in modern browsers).
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/** `POST /api/v1/billing/checkout` — returns a Stripe Checkout URL. */
export function createCheckout(body: CheckoutRequest, token: string) {
  return apiPost<CheckoutResponse>('/v1/billing/checkout', body, {
    token,
    headers: { 'X-Idempotency-Key': newIdempotencyKey() },
  });
}

/** `GET /api/v1/billing/status` — current subscription state. */
export function fetchBillingStatus(token: string) {
  return apiGet<BillingStatusResponse>('/v1/billing/status', { token });
}

/** `POST /api/v1/billing/sync` — reconciles state with Stripe after checkout. */
export function syncBilling(token: string) {
  return apiPost<BillingStatusResponse>('/v1/billing/sync', {}, { token });
}

/** `POST /api/v1/billing/portal` — Stripe Customer Portal URL. */
export function createCustomerPortal(token: string) {
  return apiPost<CustomerPortalResponse>('/v1/billing/portal', {}, { token });
}
