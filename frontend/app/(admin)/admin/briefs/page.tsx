import { AdminBriefsScreen } from '@/components/admin';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Briefs — HiddenAlerts CMS',
};

export default function AdminBriefsPage() {
  return <AdminBriefsScreen />;
}
