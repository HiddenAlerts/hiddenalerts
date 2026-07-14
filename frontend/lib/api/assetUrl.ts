import { API_BASE_URL } from './client';

/**
 * Real backend host serving uploaded media (featured images, etc). Matches
 * `API_PROXY_TARGET` in `next.config.ts` — used as a fallback for dev, where
 * `API_BASE_URL` is a relative proxy path rather than an absolute host.
 */
const FALLBACK_ASSET_ORIGIN = 'https://api.hiddenalerts.com';

function assetOrigin(): string {
  if (/^https?:\/\//i.test(API_BASE_URL)) {
    // Strip a trailing "/api" segment (if present) to get the site root.
    return API_BASE_URL.replace(/\/api\/?$/, '');
  }
  return FALLBACK_ASSET_ORIGIN;
}

/**
 * The backend returns media paths like `/uploads/intelligence-briefs/x.jpg`
 * relative to its own host, not ours — resolve them to an absolute URL so
 * `<img>` tags load correctly. Already-absolute URLs pass through unchanged.
 */
export function resolveAssetUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined;
  const trimmed = path.trim();
  if (!trimmed) return undefined;
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  const origin = assetOrigin();
  return `${origin}${trimmed.startsWith('/') ? '' : '/'}${trimmed}`;
}
