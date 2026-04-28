import { RiskBadge } from '@/components/alerts';
import {
  ArrowUpRight,
  Clock3,
  Eye,
  ExternalLink,
  MapPinned,
  MessageSquare,
  Newspaper,
  Search,
  Shield,
  ShieldAlert,
  TriangleAlert,
  TrendingUp,
  UserX,
  Users,
} from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Alert Detail — HiddenAlerts',
  description: 'Detailed signal intelligence view.',
};

const alertDetail = {
  riskLabel: 'HIGH',
  title: 'Crypto Investment Fraud Surge — Thousands Targeted Nationwide',
  score: 21,
  confidence: 'High',
  source: 'FBI',
  updated: '2h ago',
  affected: 'Retail Investors',
  summary:
    'The FBI has identified a nationwide surge in cryptocurrency investment scams targeting thousands of victims. Most victims were unaware they were being defrauded through social engineering tactics.',
  whyThisMatters: [
    'Scalable targeting via social media and messaging apps',
    'High number of unaware victims increases risk and financial impact',
    'Nationwide activity with potential for continued escalation',
  ],
  riskAssessment:
    'Coordinated fraud activity with high likelihood of continued targeting.',
  actionableInsight: [
    'Avoid unsolicited investment offers',
    'Verify platforms independently',
    'Avoid transferring funds under urgency pressure',
  ],
  sources: [
    {
      type: 'Primary Source',
      label: 'FBI - Operation Level Up Announcement',
      href: '#',
    },
    { type: 'Supporting Source', label: 'DOJ Press Release', href: '#' },
    { type: 'Supporting Source', label: 'FTC Consumer Alert - Crypto Scams', href: '#' },
  ],
  timeline: [
    { period: 'Apr 2026', event: 'FBI launches Operation Level Up' },
    { period: 'Apr 2026', event: '4,300+ victims identified across all 50 states' },
    { period: 'Ongoing', event: 'Investigations and victim support continues' },
  ],
  relatedSignals: [
    {
      title: 'Crypto Romance Scams Targeting Older Adults',
      score: '18',
      riskLabel: 'HIGH',
    },
    {
      title: 'AI-Generated Deepfake Investment Scams Rising',
      score: '17',
      riskLabel: 'HIGH',
    },
    {
      title: 'Business Email Compromise Campaigns Increase',
      score: '14',
      riskLabel: 'MEDIUM',
    },
  ],
} as const;

function RelatedCard({
  title,
  score,
  riskLabel,
}: {
  title: string;
  score: string;
  riskLabel: string;
}) {
  const scoreClass =
    riskLabel === 'HIGH'
      ? 'text-danger'
      : riskLabel === 'MEDIUM'
        ? 'text-warning'
        : 'text-success';

  return (
    <article className="border-border bg-surface/60 hover:border-primary-500/45 rounded-sm border p-4 transition-colors">
      <RiskBadge label={riskLabel} className="mb-2 px-2 py-0.5" />
      <h3 className="text-foreground line-clamp-2 text-[1.45rem] leading-tight font-semibold tracking-tight">
        {title}
      </h3>
      <p className="mt-3 text-lg font-semibold">
        <span className="text-body/85">Score </span>
        <span className={scoreClass}>{score}</span>
      </p>
    </article>
  );
}

export default function AlertDetailPage() {
  return (
    <div className="bg-background text-foreground min-h-screen px-6 py-8">
      <div className="mb-3">
        <Link
          href="/alerts"
          className="text-muted hover:text-foreground text-sm transition-colors"
        >
          ← Back to alerts
        </Link>
      </div>

      <header className="border-border bg-surface/55 mb-6 rounded-sm border px-5 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <RiskBadge label={alertDetail.riskLabel} className="px-2 py-1" />
            <h1 className="font-heading text-foreground mt-2 max-w-4xl text-2xl leading-tight font-semibold tracking-tight">
              {alertDetail.title}
            </h1>
          </div>

          <div className="shrink-0 text-right">
            <p className="text-muted text-xs font-semibold tracking-[0.12em] uppercase">
              Score
            </p>
            <p className="text-danger mt-1 text-5xl leading-none font-bold tabular-nums">
              {alertDetail.score}
            </p>
          </div>
        </div>

        <div className="text-body/90 mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <span className="inline-flex items-center gap-2">
            <Eye className="text-success/90 size-4" aria-hidden="true" />
            Confidence: {alertDetail.confidence}
          </span>
          <span className="inline-flex items-center gap-2">
            <Newspaper className="text-info/90 size-4" aria-hidden="true" />
            Source: {alertDetail.source}
          </span>
          <span className="inline-flex items-center gap-2">
            <Clock3 className="text-warning/90 size-4" aria-hidden="true" />
            Updated: {alertDetail.updated}
          </span>
          <span className="inline-flex items-center gap-2">
            <Users className="text-body/80 size-4" aria-hidden="true" />
            Affected: {alertDetail.affected}
          </span>
        </div>
      </header>

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-2 text-sm font-semibold tracking-[0.12em] uppercase">
            Signal Summary
          </h2>
          <p className="text-body/95 text-[1.02rem] leading-relaxed">
            {alertDetail.summary}
          </p>
        </div>
      </section>

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-2 text-sm font-semibold tracking-[0.12em] uppercase">
            Why This Matters
          </h2>
          <ul className="space-y-2">
            {alertDetail.whyThisMatters.map(item => (
              <li key={item} className="text-body/95 flex items-start gap-3 text-lg">
                <span className="text-danger mt-1.5 text-sm leading-none">●</span>
                <span className="text-base leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-3 text-sm font-semibold tracking-[0.12em] uppercase">
            Key Intelligence
          </h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
              <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                <Users className="text-info size-4" aria-hidden="true" />
                Victims Identified
              </div>
              <p className="text-foreground mt-1 text-2xl leading-tight font-semibold tracking-tight">
                4,300+
              </p>
            </article>

            <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
              <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                <MapPinned className="text-success size-4" aria-hidden="true" />
                Geographic Scope
              </div>
              <p className="text-success mt-1 text-2xl leading-tight font-semibold tracking-tight">
                Nationwide (U.S.)
              </p>
            </article>

            <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
              <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                <ShieldAlert className="text-warning size-4" aria-hidden="true" />
                Fraud Type
              </div>
              <p className="text-foreground mt-1 text-2xl leading-tight font-semibold tracking-tight">
                Crypto Investment Scam
              </p>
            </article>

            <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
              <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                <MessageSquare className="text-info size-4" aria-hidden="true" />
                Primary Channels
              </div>
              <p className="text-info mt-1 text-2xl leading-tight font-semibold tracking-tight">
                Social Media, Messaging Apps
              </p>
            </article>

            <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
              <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                <UserX className="text-danger size-4" aria-hidden="true" />
                Victim Awareness
              </div>
              <p className="text-danger mt-1 text-2xl leading-tight font-semibold tracking-tight">
                76% unaware
              </p>
            </article>

            <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
              <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                <TrendingUp className="text-danger size-4" aria-hidden="true" />
                Trend
              </div>
              <p className="text-foreground mt-1 text-2xl leading-tight font-semibold tracking-tight">
                Rising
              </p>
            </article>
          </div>
        </div>
      </section>

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-3 text-sm font-semibold tracking-[0.12em] uppercase">
            Risk Assessment
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-[180px_minmax(0,1fr)]">
            <div className="border-border/80 bg-surface/60 rounded-sm border px-4 py-3 md:border-r md:rounded-none md:border-y-0 md:border-l-0 md:bg-transparent">
              <p className="text-body/80 text-sm font-medium">Risk Level</p>
              <p className="text-danger mt-1 text-4xl font-bold tracking-tight">HIGH</p>
            </div>
            <p className="text-body/95 text-[1.02rem] leading-relaxed">
              The scale and distribution of victims suggest coordinated fraud
              operations with scalable targeting methods. Continued activity is
              likely in the near term.
            </p>
          </div>
        </div>
      </section>

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-3 text-sm font-semibold tracking-[0.12em] uppercase">
            Actionable Insight
          </h2>
          <div className="grid grid-cols-1 divide-y divide-border md:grid-cols-3 md:divide-x md:divide-y-0">
            <article className="px-4 py-3 text-center">
              <Shield className="text-success/90 mx-auto mb-2 size-7" aria-hidden="true" />
              <p className="text-body/95 text-[1.02rem] leading-snug">
                {alertDetail.actionableInsight[0]}
              </p>
            </article>
            <article className="px-4 py-3 text-center">
              <Search className="text-warning/90 mx-auto mb-2 size-7" aria-hidden="true" />
              <p className="text-body/95 text-[1.02rem] leading-snug">
                {alertDetail.actionableInsight[1]}
              </p>
            </article>
            <article className="px-4 py-3 text-center">
              <TriangleAlert className="text-warning/90 mx-auto mb-2 size-7" aria-hidden="true" />
              <p className="text-body/95 text-[1.02rem] leading-snug">
                {alertDetail.actionableInsight[2]}
              </p>
            </article>
          </div>
        </div>
      </section>

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-3 text-sm font-semibold tracking-[0.12em] uppercase">
            Sources
          </h2>
          <ul className="divide-border space-y-0 divide-y">
            {alertDetail.sources.map(source => (
              <li key={source.label} className="flex items-center justify-between gap-4 py-3">
                <div className="min-w-0">
                  <p className="text-muted text-xs font-semibold tracking-wide uppercase">
                    {source.type}
                  </p>
                  <p className="text-body/95 truncate text-[1.02rem] font-medium">
                    {source.label}
                  </p>
                </div>
                <a
                  href={source.href}
                  className="text-info hover:text-info/80 inline-flex shrink-0 items-center gap-1.5 text-sm font-semibold transition-colors"
                >
                  View Source
                  <ExternalLink className="size-3.5" aria-hidden="true" />
                </a>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-3 text-sm font-semibold tracking-[0.12em] uppercase">
            Timeline
          </h2>
          <ul className="space-y-3">
            {alertDetail.timeline.map(item => (
              <li key={item.event} className="flex items-start gap-4">
                <span className="bg-muted/70 mt-2 size-2.5 shrink-0 rounded-full" />
                <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-[110px_minmax(0,1fr)]">
                  <p className="text-body/85 text-[1.02rem] font-medium">{item.period}</p>
                  <p className="text-body/95 text-[1.02rem]">{item.event}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-muted text-sm font-semibold tracking-[0.12em] uppercase">
              Related Signals
            </h2>
            <button
              type="button"
              className="text-info hover:text-info/80 inline-flex items-center gap-1 text-sm font-semibold transition-colors"
            >
              View All
              <ArrowUpRight className="size-3.5" aria-hidden="true" />
            </button>
          </div>

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            {alertDetail.relatedSignals.map(signal => (
              <RelatedCard
                key={signal.title}
                title={signal.title}
                score={signal.score}
                riskLabel={signal.riskLabel}
              />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
