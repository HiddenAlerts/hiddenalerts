import type { LucideIcon } from 'lucide-react';
import {
  Building2,
  Eye,
  Globe2,
  Laptop,
  Scale,
  Shield,
  ShieldAlert,
  UserRound,
} from 'lucide-react';

/**
 * Ken’s coverage areas — display-only on Dashboard + Brief Library sidebar.
 * Not driven by tag counts (those stay as category filters).
 */
export type CoverageArea = {
  id: string;
  label: string;
  icon: LucideIcon;
};

export const COVERAGE_AREAS: ReadonlyArray<CoverageArea> = [
  { id: 'financial-crime', label: 'Financial Crime', icon: Building2 },
  { id: 'consumer-fraud', label: 'Consumer Fraud', icon: UserRound },
  { id: 'cybercrime', label: 'Cybercrime', icon: Laptop },
  { id: 'aml-bsa', label: 'AML / BSA', icon: Shield },
  { id: 'regulatory', label: 'Regulatory Enforcement', icon: Scale },
  { id: 'sanctions', label: 'Sanctions', icon: ShieldAlert },
  { id: 'insider-threat', label: 'Insider Threat', icon: Eye },
  { id: 'emerging-threats', label: 'Emerging Threats', icon: Globe2 },
];

/** @deprecated Prefer `COVERAGE_AREAS` — kept for existing dashboard imports. */
export type DashboardCoverageArea = CoverageArea;
export const DASHBOARD_COVERAGE_AREAS = COVERAGE_AREAS;
