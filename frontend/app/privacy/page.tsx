import { LegalPage } from '@/components/legal/LegalPage';
import { privacyDocument } from '@/content/legal/privacy';

import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: `${privacyDocument.title} — HiddenAlerts`,
};

export default function PrivacyPage() {
  return <LegalPage document={privacyDocument} />;
}
