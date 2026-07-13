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

/** Display-only coverage areas for the dashboard (Ken’s recommended set). */
export type DashboardCoverageArea = {
  id: string;
  label: string;
  icon: LucideIcon;
};

export const DASHBOARD_COVERAGE_AREAS: ReadonlyArray<DashboardCoverageArea> = [
  { id: 'financial-crime', label: 'Financial Crime', icon: Building2 },
  { id: 'consumer-fraud', label: 'Consumer Fraud', icon: UserRound },
  { id: 'cybercrime', label: 'Cybercrime', icon: Laptop },
  { id: 'aml-bsa', label: 'AML / BSA', icon: Shield },
  { id: 'regulatory', label: 'Regulatory Enforcement', icon: Scale },
  { id: 'sanctions', label: 'Sanctions', icon: ShieldAlert },
  { id: 'insider-threat', label: 'Insider Threat', icon: Eye },
  { id: 'emerging-threats', label: 'Emerging Threats', icon: Globe2 },
];
