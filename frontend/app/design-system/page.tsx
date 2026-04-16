import { Button, Input, Tag, Typography } from '@/components';
import { ArrowRight, Mail, Search } from 'lucide-react';
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
        <Section title="Typography · scale">
          <div className="flex max-w-3xl flex-col gap-4">
            <Typography variant="h1">Heading 1</Typography>
            <Typography variant="h2">Heading 2</Typography>
            <Typography variant="h3">Heading 3</Typography>
            <Typography variant="h4">Heading 4</Typography>
            <Typography variant="h5">Heading 5</Typography>
            <Typography variant="h6">Heading 6</Typography>
            <Typography variant="body1">
              Body large — intelligence alerts
            </Typography>
            <Typography variant="body2">
              Body default — supporting copy for the dashboard.
            </Typography>
            <Typography variant="body3">
              Body small — meta and dense UI.
            </Typography>
            <Typography variant="caption">
              Caption — labels and timestamps
            </Typography>
            <Typography variant="footer">Footer — fine print</Typography>
          </div>
        </Section>

        <Section title="Tag · types · round">
          <p className="text-muted mb-3 text-sm">Pill shape with optional leading dot.</p>
          <div className="flex flex-wrap items-center gap-3">
            <Tag title="Gray" type="gray" shape="round" />
            <Tag title="Gray light" type="grayLight" shape="round" />
            <Tag title="Primary" type="primary" shape="round" />
            <Tag title="Info" type="info" shape="round" />
            <Tag title="Success" type="success" shape="round" />
            <Tag title="Warning" type="warning" shape="round" />
            <Tag title="Danger" type="danger" shape="round" />
          </div>
        </Section>

        <Section title="Tag · types · square">
          <p className="text-muted mb-3 text-sm">
            Subtle radius; dot is omitted for square (pill-only).
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Tag title="Gray" type="gray" shape="square" />
            <Tag title="Gray light" type="grayLight" shape="square" />
            <Tag title="Primary" type="primary" shape="square" />
            <Tag title="Info" type="info" shape="square" />
            <Tag title="Success" type="success" shape="square" />
            <Tag title="Warning" type="warning" shape="square" />
            <Tag title="Danger" type="danger" shape="square" />
          </div>
        </Section>

        <Section title="Tag · sizes & shapes">
          <div className="flex flex-col gap-6">
            <div>
              <p className="text-muted mb-3 text-sm font-medium">Round</p>
              <div className="flex flex-wrap items-center gap-3">
                <Tag title="Small" size="sm" shape="round" type="success" />
                <Tag title="Large" size="lg" shape="round" type="success" />
                <Tag title="No dot" dot={false} shape="round" type="success" />
              </div>
            </div>
            <div>
              <p className="text-muted mb-3 text-sm font-medium">Square</p>
              <div className="flex flex-wrap items-center gap-3">
                <Tag title="Small" size="sm" shape="square" type="info" />
                <Tag title="Large" size="lg" shape="square" type="info" />
                <Tag title="No dot" dot={false} shape="square" type="info" />
              </div>
            </div>
          </div>
        </Section>

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

        <Section title="Input · sizes">
          <div className="flex max-w-md flex-col gap-3">
            <Input placeholder="Extra small" inputSize="xs" />
            <Input placeholder="Small" inputSize="sm" />
            <Input placeholder="Medium (default)" inputSize="md" />
            <Input placeholder="Large" inputSize="lg" />
          </div>
        </Section>

        <Section title="Input · states">
          <div className="flex max-w-md flex-col gap-3">
            <Input placeholder="Default" />
            <Input placeholder="With value" defaultValue="hiddenalerts.io" />
            <Input
              placeholder="Error"
              isError
              errorMessage="This field has an error."
            />
            <Input placeholder="Disabled" disabled />
          </div>
        </Section>

        <Section title="Input · label & password">
          <div className="flex max-w-md flex-col gap-3">
            <Input
              name="email"
              label="Email"
              type="email"
              placeholder="you@example.com"
              required
              addAsterisk
            />
            <Input
              name="password"
              label="Password"
              type="password"
              placeholder="••••••••"
              passwordWithIcon
            />
          </div>
        </Section>

        <Section title="Input · with left icon">
          <div className="flex max-w-md flex-col gap-3">
            <Input
              type="search"
              placeholder="Search…"
              leftIcon={<Search />}
              aria-label="Search"
            />
          </div>
        </Section>
      </div>
    </main>
  );
}
