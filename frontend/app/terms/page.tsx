import { LegalPage } from '@/components/legal/LegalPage';
import { termsDocument } from '@/content/legal/terms';

import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: `${termsDocument.title} — HiddenAlerts`,
};

export default function TermsPage() {
  return <LegalPage document={termsDocument} />;
}
