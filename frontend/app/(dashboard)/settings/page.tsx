import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Settings — HiddenAlerts',
};

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <h1 className="font-heading text-foreground text-2xl font-semibold tracking-tight">
        Settings
      </h1>
      <p className="text-muted text-sm">
        Workspace settings will appear here.
      </p>
    </div>
  );
}
