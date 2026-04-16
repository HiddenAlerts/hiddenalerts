import { Button } from '@/components';
import { ArrowRight, Mail } from 'lucide-react';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Design system — HiddenAlerts',
  description: 'Design system and component previews for HiddenAlerts.',
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-4">
      <h2 className="font-figtree text-foreground text-xl font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function DesignSystemPage() {
  return (
    <main className="mx-auto min-h-full max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="border-border space-y-2 border-b pb-8">
        <p className="caption">HiddenAlerts · internal</p>
        <h1>Design system</h1>
        <p className="text-muted max-w-2xl">
          Component previews. Use this page to verify variants and states.
        </p>
      </header>

      <div className="mt-10 space-y-12">
        <Section title="Button · variants">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="default">Default</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="link">Link</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="danger">Danger</Button>
            <Button variant="danger-link">Danger link</Button>
          </div>
        </Section>

        <Section title="Button · sizes">
          <div className="flex flex-wrap items-center gap-3">
            <Button size="lg">Large</Button>
            <Button size="md">Medium</Button>
            <Button size="sm">Small</Button>
            <Button size="xs">Extra small</Button>
          </div>
        </Section>

        <Section title="Button · with icons">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="default"
              leftIcon={<Mail className="size-4 shrink-0" aria-hidden />}
            >
              Email
            </Button>
            <Button
              variant="outline"
              rightIcon={<ArrowRight className="size-4 shrink-0" aria-hidden />}
            >
              Continue
            </Button>
          </div>
        </Section>

        <Section title="Button · loading">
          <div className="flex flex-wrap items-center gap-3">
            <Button loading aria-label="Submitting" />
            <Button variant="outline" loading aria-label="Submitting" />
            <Button variant="secondary" loading aria-label="Submitting" />
            <Button variant="danger" loading aria-label="Submitting" />
          </div>
        </Section>

        <Section title="Button · disabled">
          <div className="flex flex-wrap items-center gap-3">
            <Button disabled>Disabled</Button>
            <Button variant="outline" disabled>
              Disabled
            </Button>
            <Button variant="link" disabled>
              Disabled
            </Button>
          </div>
        </Section>
      </div>
    </main>
  );
}
