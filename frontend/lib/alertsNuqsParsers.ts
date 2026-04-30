import {
  API_ALERT_CATEGORY_OPTIONS,
  type AlertsCategoryFilterValue,
} from '@/data/apiAlertCategories';
import {
  ALERTS_RISK_FILTER_OPTIONS,
  type AlertsRiskFilterValue,
} from '@/data/alertRiskFilterOptions';
import { parseAsInteger, parseAsStringLiteral } from 'nuqs';

const ALERT_LIST_RISK_IN_ORDER = ALERTS_RISK_FILTER_OPTIONS.map(
  o => o.value,
) as unknown as readonly [
  AlertsRiskFilterValue,
  AlertsRiskFilterValue,
  AlertsRiskFilterValue,
  AlertsRiskFilterValue,
];

const ALERT_LIST_CATEGORY_IN_ORDER = API_ALERT_CATEGORY_OPTIONS.map(
  o => o.value,
) as unknown as readonly [
  AlertsCategoryFilterValue,
  ...AlertsCategoryFilterValue[],
];

export const alertsListQueryParsers = {
  risk: parseAsStringLiteral(ALERT_LIST_RISK_IN_ORDER).withDefault('all'),
  category: parseAsStringLiteral(ALERT_LIST_CATEGORY_IN_ORDER).withDefault(
    'all',
  ),
  page: parseAsInteger.withDefault(1),
} as const;
