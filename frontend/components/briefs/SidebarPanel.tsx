import { cn } from '@/lib/utils';
import type { FC, ReactNode } from 'react';

export type SidebarPanelProps = {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
};

/** Bordered surface used by the library's right-rail informational panels. */
export const SidebarPanel: FC<SidebarPanelProps> = ({
  title,
  icon,
  children,
  className,
}) => (
  <section
    className={cn(
      'border-border bg-background-alt rounded-xl border p-4 sm:p-5',
      className,
    )}
  >
    <h2 className="text-foreground flex items-center gap-2 text-xs font-bold tracking-wide uppercase [&_svg]:size-4">
      {icon}
      {title}
    </h2>
    <div className="mt-4">{children}</div>
  </section>
);
