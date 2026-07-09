import { AdminBriefDetailScreen } from '@/components/admin';
import type { Metadata } from 'next';

type RouteParams = { briefId: string };

export const metadata: Metadata = {
  title: 'Brief — HiddenAlerts CMS',
};

export default async function AdminBriefDetailPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { briefId } = await params;
  return <AdminBriefDetailScreen briefId={briefId} />;
}
