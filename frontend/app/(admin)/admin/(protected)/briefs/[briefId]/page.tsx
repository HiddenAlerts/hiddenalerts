import { AdminBriefDetailScreen } from '@/components/admin';
import { findAdminBrief } from '@/data/adminMockBriefs';
import type { Metadata } from 'next';

type RouteParams = { briefId: string };

export async function generateMetadata({
  params,
}: {
  params: Promise<RouteParams>;
}): Promise<Metadata> {
  const { briefId } = await params;
  const brief = findAdminBrief(briefId);
  return {
    title: brief
      ? `${brief.title} — HiddenAlerts CMS`
      : 'Brief — HiddenAlerts CMS',
  };
}

export default async function AdminBriefDetailPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { briefId } = await params;
  return <AdminBriefDetailScreen briefId={briefId} />;
}
