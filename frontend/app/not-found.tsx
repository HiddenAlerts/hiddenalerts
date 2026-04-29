import { BrandedIssueScreen } from '@/components/errors/BrandedIssueScreen';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Page not found — HiddenAlerts',
  description: 'The page you are looking for does not exist.',
};

export default function NotFound() {
  return (
    <BrandedIssueScreen
      code="404"
      title="Page not found"
      description="That URL does not match any page. Check the address or go back to the home page."
    />
  );
}
