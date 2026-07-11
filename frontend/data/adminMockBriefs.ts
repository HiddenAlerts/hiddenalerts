/**
 * Lightweight mock briefs used only for the "link an alert to a brief"
 * dropdown/display on the (still mock-data) Alerts admin screens. Briefs
 * themselves are wired to the real API — see `lib/api/adminBriefs.ts`.
 */
export type AdminBriefSummary = {
  id: string;
  title: string;
};

export const ADMIN_MOCK_BRIEFS: AdminBriefSummary[] = [
  { id: 'brief-1', title: 'Caller-as-a-Service Fraud: The New Telecom Threat Landscape' },
  { id: 'brief-2', title: 'FTX Collapse — Signal Risk Patterns for Financial Institutions' },
  { id: 'brief-3', title: 'Dark Web Credential Leakage Surge Q2 2026' },
  { id: 'brief-4', title: 'Synthetic Identity Networks in Southeast Asia' },
  { id: 'brief-5', title: 'Deepfake Social Engineering Attacks on Executives' },
  { id: 'brief-6', title: 'Crypto Mixing Services Under New Sanctions Regime' },
  { id: 'brief-7', title: 'Sanctions Evasion via Shell Companies in Eastern Europe' },
  { id: 'brief-8', title: 'Phishing Campaign Targets Regional Bank Customers' },
  { id: 'brief-9', title: 'Insider Trading Signals in Tech Sector IPOs' },
  { id: 'brief-10', title: 'Cross-Border Payment Fraud via Mule Accounts' },
  { id: 'brief-11', title: 'AI-Generated Fake KYC Documents on the Rise' },
  { id: 'brief-12', title: 'Ransomware Crews Pivoting to Data Extortion Models' },
];

export function findAdminBrief(id: string): AdminBriefSummary | undefined {
  return ADMIN_MOCK_BRIEFS.find(b => b.id === id);
}
