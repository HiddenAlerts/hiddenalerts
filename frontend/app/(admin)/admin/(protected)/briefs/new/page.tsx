import { AdminBriefForm } from '@/components/admin';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'New Brief — HiddenAlerts CMS',
};

export default function AdminBriefNewPage() {
  return (
    <AdminBriefForm
      title="Create Intelligence Brief"
      subtitle="All fields marked with * are required to publish. Drafts only need a title."
      returnHref="/admin/briefs"
    />
  );
}
