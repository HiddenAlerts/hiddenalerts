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

export const alertsListQueryParsers = {
  risk: parseAsStringLiteral(ALERT_LIST_RISK_IN_ORDER).withDefault('all'),
  page: parseAsInteger.withDefault(1),
} as const;
