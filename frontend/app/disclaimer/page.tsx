import { LegalPage } from '@/components/legal/LegalPage';
import { disclaimerDocument } from '@/content/legal/disclaimer';

import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: `${disclaimerDocument.title} — HiddenAlerts`,
};

export default function DisclaimerPage() {
  return <LegalPage document={disclaimerDocument} />;
}
