import {
  BellRing,
  BriefcaseBusiness,
  Building2,
  DatabaseZap,
  FileSearch,
  Landmark,
  Radar,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
// import { WaitlistForm } from './WaitlistForm';

type AlertCardProps = {
  level: 'HIGH' | 'MEDIUM';
  source: string;
  timeAgo: string;
  title: string;
  description: string;
};

function SectionBlock({
  icon,
  title,
  sectionTone,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  sectionTone: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className={`border-border-subtle border-t px-4 py-16 sm:px-6 sm:py-20 lg:px-8 ${sectionTone}`}
    >
      <div className="mx-auto max-w-3xl">
        <div className="bg-primary-500/12 text-primary-300 mx-auto flex size-11 items-center justify-center rounded-full border border-white/10">
          {icon}
        </div>
        <h2 className="font-heading text-foreground mt-3 text-center text-2xl font-semibold tracking-tight sm:text-3xl">
          {title}
        </h2>
        <div className="mt-4">{children}</div>
      </div>
    </section>
  );
}

function AlertCard({ level, source, timeAgo, title, description }: AlertCardProps) {
  const isHigh = level === 'HIGH';

  return (
    <article className="border-border bg-surface/55 rounded-xl border p-4 sm:p-5">
      <div className="text-muted flex flex-wrap items-center justify-between gap-2 text-sm">
        <p className="flex items-center gap-2 font-medium">
          <span aria-hidden>{isHigh ? '🔴' : '🟠'}</span>
          <span className={isHigh ? 'text-danger' : 'text-warning'}>{level}</span>
          <span>— {source}</span>
          <span>— {timeAgo}</span>
        </p>
      </div>
      <h3 className="text-foreground mt-2 text-lg font-semibold">{title}</h3>
      <p className="text-body mt-2 text-sm sm:text-base">{description}</p>
    </article>
  );
}

const solutionBullets = [
  'Aggregates signals from trusted sources (DOJ, SEC, FBI)',
  'Ranks alerts by risk level (High, Medium, Low)',
  'Delivers only what matters — no noise',
] as const;

const sourceBullets = [
  {
    title: 'DOJ enforcement actions',
    description: 'Case filings, charges, and outcomes tied to fraud enforcement.',
    icon: Landmark,
  },
  {
    title: 'SEC filings and investigations',
    description:
      'Disclosures and actions that flag potential market and compliance risk.',
    icon: FileSearch,
  },
  {
    title: 'Federal and public data sources',
    description:
      'Trusted open datasets and agency records that reveal emerging patterns.',
    icon: ShieldCheck,
  },
] as const;

const sourceCards = [
  {
    title: 'DOJ actions',
    description: 'Criminal complaints, indictments, and enforcement updates.',
    icon: Scale,
  },
  {
    title: 'SEC filings',
    description: 'Regulatory disclosures, investigations, and market risk clues.',
    icon: FileSearch,
  },
  {
    title: 'Public sources',
    description: 'Open records and trusted databases that reveal early patterns.',
    icon: DatabaseZap,
  },
] as const;

const NEWSLETTER_URL = 'https://hiddenalerts.beehiiv.com';

export function LandingContentSections() {
  return (
    <>
      <SectionBlock
        icon={<ShieldAlert className="size-5" aria-hidden />}
        title="Most fraud signals are missed early"
        sectionTone="bg-[radial-gradient(circle_at_15%_10%,rgba(59,130,246,0.14),transparent_38%),radial-gradient(circle_at_85%_90%,rgba(56,189,248,0.10),transparent_42%)]"
      >
        <p className="text-body text-center text-base leading-relaxed sm:text-lg">
          By the time fraud reaches the news, the damage is already done.
          <br />
          Critical signals appear hours or days earlier — scattered across filings,
          enforcement actions, and obscure sources.
        </p>
        <div className="mt-7 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {sourceCards.map((card) => {
            const Icon = card.icon;
            return (
              <article
                key={card.title}
                className="border-border bg-[linear-gradient(165deg,rgba(255,255,255,0.08),rgba(255,255,255,0.02))] rounded-xl border px-4 py-4 text-left shadow-[0_4px_22px_rgba(0,0,0,0.22)]"
              >
                <div className="bg-primary-500/14 text-primary-300 mb-3 inline-flex size-9 items-center justify-center rounded-lg border border-white/10">
                  <Icon className="size-4" aria-hidden />
                </div>
                <h3 className="text-foreground text-sm font-semibold sm:text-base">
                  {card.title}
                </h3>
                <p className="text-body mt-1 text-xs leading-relaxed sm:text-sm">
                  {card.description}
                </p>
              </article>
            );
          })}
        </div>
      </SectionBlock>

      <SectionBlock
        icon={<Radar className="size-5" aria-hidden />}
        title="HiddenAlerts surfaces early risk signals"
        sectionTone="bg-[linear-gradient(180deg,rgba(15,23,42,0.58),rgba(15,23,42,0.32))]"
      >
        <ul className="mx-auto mt-1 max-w-2xl space-y-3">
          {solutionBullets.map((item) => (
            <li
              key={item}
              className="border-border bg-surface/45 text-body flex items-start gap-3 rounded-lg border px-4 py-3"
            >
              <ShieldCheck className="text-primary-400 mt-0.5 size-4 shrink-0" aria-hidden />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </SectionBlock>

      <SectionBlock
        icon={<BellRing className="size-5" aria-hidden />}
        title="Live intelligence feed"
        sectionTone="bg-[radial-gradient(circle_at_85%_15%,rgba(59,130,246,0.10),transparent_36%)]"
      >
        <div className="mx-auto max-w-2xl space-y-3">
          <AlertCard
            level="HIGH"
            source="DOJ"
            timeAgo="2 hours ago"
            title="$19M Wire Fraud Scheme — Multi-State Operation"
            description="Coordinated fraud ring expanding across multiple states."
          />
          <AlertCard
            level="MEDIUM"
            source="SEC"
            timeAgo="5 hours ago"
            title="Investment Scam Targeting Retirees"
            description="Pattern of targeted financial exploitation increasing."
          />
        </div>
      </SectionBlock>

      <SectionBlock
        icon={<Building2 className="size-5" aria-hidden />}
        title="Built from trusted sources"
        sectionTone="bg-[linear-gradient(180deg,rgba(30,41,59,0.46),rgba(30,41,59,0.22))]"
      >
        <p className="text-body text-center text-base leading-relaxed sm:text-lg">
          HiddenAlerts monitors signals from:
        </p>
        <ul className="mx-auto mt-7 grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-3">
          {sourceBullets.map((source) => (
            <li
              key={source.title}
              className="border-border bg-[linear-gradient(165deg,rgba(255,255,255,0.08),rgba(255,255,255,0.02))] rounded-xl border px-4 py-4 text-left shadow-[0_4px_22px_rgba(0,0,0,0.22)]"
            >
              <div className="bg-primary-500/14 text-primary-300 mb-3 inline-flex size-9 items-center justify-center rounded-lg border border-white/10">
                <source.icon className="size-4" aria-hidden />
              </div>
              <h3 className="text-foreground text-sm font-semibold sm:text-base">
                {source.title}
              </h3>
              <p className="text-body mt-1 text-xs leading-relaxed sm:text-sm">
                {source.description}
              </p>
            </li>
          ))}
        </ul>
      </SectionBlock>

      <SectionBlock
        icon={<BriefcaseBusiness className="size-5" aria-hidden />}
        title="Designed for financial crime and risk professionals"
        sectionTone="bg-[radial-gradient(circle_at_10%_85%,rgba(34,197,94,0.08),transparent_34%)]"
      >
        <p className="text-body text-center text-base leading-relaxed sm:text-lg">
          Built for investigators, analysts, and compliance teams who need early
          visibility into emerging fraud threats — before they escalate.
        </p>
      </SectionBlock>

      <section className="border-border-subtle bg-[linear-gradient(180deg,rgba(30,41,59,0.38),rgba(15,23,42,0.32))] border-t px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <div className="bg-primary-500/12 text-primary-300 mx-auto flex size-11 items-center justify-center rounded-full border border-white/10">
            <Sparkles className="size-5" aria-hidden />
          </div>
          <h2 className="font-heading text-foreground mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">
            Stay ahead of financial threats
          </h2>
          <div className="mt-6">
            <a
              href={NEWSLETTER_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                buttonVariants({ variant: 'default', size: 'md' }),
                'inline-flex h-11 min-w-[220px] items-center justify-center py-0',
              )}
            >
              Subscribe to newsletter
            </a>
            {/* <WaitlistForm
              formId="waitlist-final"
              microText="Be among the first to access real-time fraud intelligence."
            /> */}
          </div>
        </div>
      </section>
    </>
  );
}
