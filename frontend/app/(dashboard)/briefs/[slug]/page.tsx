import { BriefReader } from '@/components/briefs';
import { findBriefDetailBySlug } from '@/data/subscriberBriefDetails';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

type RouteParams = { slug: string };

export async function generateMetadata({
  params,
}: {
  params: Promise<RouteParams>;
}): Promise<Metadata> {
  const { slug } = await params;
  const brief = findBriefDetailBySlug(slug);
  return { title: brief ? `${brief.title} — HiddenAlerts` : 'Brief Not Found' };
}

export default async function BriefDetailPage({
  params,
}: {
  params: Promise<RouteParams>;
}) {
  const { slug } = await params;
  const brief = findBriefDetailBySlug(slug);
  if (!brief) notFound();

  return (
    <div className="border-border bg-background-alt overflow-hidden rounded-xl border">
      <BriefReader brief={brief} topBar="subscriber" />
    </div>
  );
}
