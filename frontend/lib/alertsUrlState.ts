/**
 * Serializes and validates the alerts list query used in `from` (detail → list).
 * Live list `risk` / `category` / `page` sync is handled by `nuqs` in `AlertsScreen`.
 */
import { API_ALERT_CATEGORY_OPTIONS } from '@/data/apiAlertCategories';
import { ALERTS_RISK_FILTER_OPTIONS } from '@/data/alertRiskFilterOptions';

const ALLOWED_RISK = new Set(
  ALERTS_RISK_FILTER_OPTIONS.map(o => o.value),
) as ReadonlySet<string>;

const ALLOWED_CATEGORY = new Set(
  API_ALERT_CATEGORY_OPTIONS.map(o => o.value),
) as ReadonlySet<string>;

const MAX_PAGE = 10_000;

export function normalizeAlertsRiskFromSearchParams(raw: string | null): string {
  const v = (raw ?? '').trim().toLowerCase();
  if (!v) return 'all';
  if (ALLOWED_RISK.has(v)) return v;
  return 'all';
}

/** Exact match on category label (e.g. `Money Laundering`). */
export function normalizeAlertsCategoryFromSearchParams(
  raw: string | null,
): string {
  const v = (raw ?? '').trim();
  if (!v) return 'all';
  const lower = v.toLowerCase();
  if (lower === 'all') return 'all';
  if (ALLOWED_CATEGORY.has(v)) return v;
  return 'all';
}

export function parseAlertsPageFromSearchParams(raw: string | null): number {
  const p = Number.parseInt(String(raw ?? ''), 10);
  if (Number.isNaN(p) || p < 1) return 1;
  return Math.min(p, MAX_PAGE);
}

/**
 * Query string fragment for `/alerts` (no leading `?`).
 * Omits defaults: all risks, all categories, page 1.
 */
export function buildAlertsListQueryString(
  risk: string,
  page: number,
  category: string = 'all',
): string {
  const riskNorm = normalizeAlertsRiskFromSearchParams(risk);
  const categoryNorm = normalizeAlertsCategoryFromSearchParams(category);
  const pageNorm = Math.max(1, Math.min(Math.floor(page), MAX_PAGE));

  const params = new URLSearchParams();
  if (riskNorm !== 'all') params.set('risk', riskNorm);
  if (categoryNorm !== 'all') params.set('category', categoryNorm);
  if (pageNorm > 1) params.set('page', String(pageNorm));
  return params.toString();
}

/**
 * Validates `from` on alert detail URLs (encoded list query).
 * Only `risk`, `category`, and `page` are honored; unknown keys are dropped.
 */
export function sanitizeAlertsReturnQueryString(encoded: string | null): string | null {
  if (!encoded?.trim()) return null;
  try {
    const decoded = decodeURIComponent(encoded.trim());
    const probe = new URLSearchParams(decoded);
    const risk = normalizeAlertsRiskFromSearchParams(probe.get('risk'));
    const category = normalizeAlertsCategoryFromSearchParams(
      probe.get('category'),
    );
    const page = parseAlertsPageFromSearchParams(probe.get('page'));
    const qs = buildAlertsListQueryString(risk, page, category);
    return qs === '' ? null : qs;
  } catch {
    return null;
  }
}

export function alertsListHrefFromReturnParam(fromParam: string | null): string {
  const qs = sanitizeAlertsReturnQueryString(fromParam);
  return qs ? `/alerts?${qs}` : '/alerts';
}
