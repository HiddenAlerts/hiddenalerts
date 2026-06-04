import { AdminBriefForm } from '@/components/admin';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'New Brief — HiddenAlerts CMS',
};

export default function AdminBriefNewPage() {
  return (
    <AdminBriefForm
      title="Create Brief"
      subtitle="Add a new intelligence brief"
      returnHref="/admin/briefs"
    />
  );
}
