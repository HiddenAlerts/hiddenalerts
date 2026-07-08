import { AdminBriefForm } from '@/components/admin';
import { findAdminBrief } from '@/data/adminMockBriefs';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

type RouteParams = { briefId: string };

export const metadata: Metadata = {
  title: 'Edit Brief — HiddenAlerts CMS',
};

export default async function AdminBriefEditPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { briefId } = await params;
  const brief = findAdminBrief(briefId);
  if (!brief) notFound();

  return (
    <AdminBriefForm
      initial={brief}
      title="Edit Intelligence Brief"
      subtitle="All fields marked with * are required."
      returnHref={`/admin/briefs/${brief.id}`}
    />
  );
}
