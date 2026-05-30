import type {
  SubscriberAccessResponse,
  SubscriberMeResponse,
} from '@/types/subscriber';

import { apiGet } from './client';

/** `GET /api/v1/subscriber/me` */
export function fetchSubscriberMe(token: string) {
  return apiGet<SubscriberMeResponse>('/v1/subscriber/me', { token });
}

/** `GET /api/v1/subscriber/access` */
export function fetchSubscriberAccess(token: string) {
  return apiGet<SubscriberAccessResponse>('/v1/subscriber/access', { token });
}
