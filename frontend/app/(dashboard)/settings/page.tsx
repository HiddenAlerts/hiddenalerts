import { ComingSoon } from '@/components';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Settings — HiddenAlerts',
};

export default function SettingsPage() {
  return (
    <ComingSoon
      title="Settings (Coming Soon)"
      description="Customize alert preferences, risk thresholds, and intelligence feeds."
    />
  );
}
