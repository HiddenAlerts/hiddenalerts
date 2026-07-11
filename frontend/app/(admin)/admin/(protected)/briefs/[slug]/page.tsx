import { AdminBriefDetailScreen } from '@/components/admin';
import type { Metadata } from 'next';

type RouteParams = { slug: string };

export const metadata: Metadata = {
  title: 'Brief — HiddenAlerts CMS',
};

export default async function AdminBriefDetailPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { slug } = await params;
  return <AdminBriefDetailScreen slug={slug} />;
}
