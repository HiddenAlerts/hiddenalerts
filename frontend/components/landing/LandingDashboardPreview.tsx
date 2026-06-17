import Tag from '@/components/ui/Tag/Tag';
import { cn } from '@/lib/utils';
import { Building2, ShieldAlert, Webhook } from 'lucide-react';
import type { ReactNode } from 'react';

type RowProps = {
  icon: ReactNode;
  title: string;
  description: string;
  tag: { label: string; type: React.ComponentProps<typeof Tag>['type'] };
};

function PreviewRow({ icon, title, description, tag }: RowProps) {
  return (
    <div
      className={cn(
        'border-border flex flex-col gap-3 border-b px-4 py-3.5 last:border-b-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4',
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        <span className="bg-primary-500/10 text-primary-600 mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-md [&_svg]:size-4">
          {icon}
        </span>
        <div className="min-w-0">
          <p className="text-article-foreground font-medium">{title}</p>
          <p className="text-muted mt-0.5 text-sm leading-snug">
            {description}
          </p>
        </div>
      </div>
      <Tag
        title={tag.label}
        type={tag.type}
        size="sm"
        shape="round"
        dot
        textClassName="!text-article-foreground"
      />
    </div>
  );
}

const rows: RowProps[] = [
  {
    icon: <ShieldAlert aria-hidden />,
    title: 'Payment fraud cluster',
    description: 'New mule patterns and issuer-reported spikes.',
    tag: { label: 'High priority', type: 'danger' },
  },
  {
    icon: <Webhook aria-hidden />,
    title: 'Scam infrastructure',
    description: 'Domains, wallets, and repeat operator fingerprints.',
    tag: { label: 'Watch', type: 'warning' },
  },
  {
    icon: <Building2 aria-hidden />,
    title: 'Corporate red flags',
    description: 'Filings, related parties, and restatement risk.',
    tag: { label: 'Review', type: 'warning' },
  },
];

export function LandingDashboardPreview() {
  return (
    <section
      className="px-4 pb-12 sm:px-6 sm:pb-16 lg:px-8"
      aria-label="Product preview"
    >
      <div className="mx-auto max-w-2xl">
        <div className="border-border bg-surface-muted/50 rounded-xl border p-1 shadow-md sm:rounded-2xl">
          <div className="bg-surface-muted flex items-center gap-2 rounded-[10px] px-3 py-2 sm:rounded-[14px]">
            <span className="bg-danger size-2.5 rounded-full" aria-hidden />
            <span className="bg-warning size-2.5 rounded-full" aria-hidden />
            <span className="bg-success size-2.5 rounded-full" aria-hidden />
            <span className="text-muted ml-2 truncate text-xs">Alerts</span>
          </div>
          <div className="bg-article-bg text-article-foreground mt-1 overflow-hidden rounded-[10px] shadow-sm sm:mt-1.5 sm:rounded-[14px]">
            <div className="border-border flex items-center justify-between border-b px-4 py-3">
              <p className="text-sm font-semibold">Feed</p>
              <span className="text-muted text-xs">Sample data</span>
            </div>
            <div>
              {rows.map(row => (
                <PreviewRow key={row.title} {...row} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
