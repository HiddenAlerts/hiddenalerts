import { AdminShell } from '@/components/admin';
import { AdminGate } from '@/components/auth/AdminGate';

export default function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <AdminGate>
      <AdminShell>{children}</AdminShell>
    </AdminGate>
  );
}
