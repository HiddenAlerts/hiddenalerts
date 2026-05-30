import { SubscriberGate } from '@/components/auth/SubscriberGate';
import { DashboardShell } from '@/components/dashboard';

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <DashboardShell>
      <SubscriberGate>{children}</SubscriberGate>
    </DashboardShell>
  );
}
