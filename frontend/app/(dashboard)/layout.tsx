import { SubscriberGate } from '@/components/auth/SubscriberGate';
import { DashboardShell } from '@/components/dashboard';

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <SubscriberGate>
      <DashboardShell>{children}</DashboardShell>
    </SubscriberGate>
  );
}
