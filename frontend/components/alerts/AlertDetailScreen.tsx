'use client';

import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { useAlertDetailQuery } from '@/hooks';
import { confidenceLabelFromRisk, formatRiskLevelLabel } from '@/lib/alertDisplay';
import { alertsListHrefFromReturnParam } from '@/lib/alertsUrlState';
import { formatAlertDatePublished } from '@/lib/formatAlertDate';
import type { HttpRequestError } from '@/lib/api/client';
import type { AlertApiRecord } from '@/types/alertsApi';
import { RiskBadge } from './RiskBadge';
import {
  Clock3,
  ExternalLink,
  Eye,
  MapPinned,
  MessageSquare,
  Newspaper,
  ShieldAlert,
  Users,
} from 'lucide-react';
import Link from 'next/link';
import { useQueryState } from 'nuqs';
import { useMemo } from 'react';

type AlertDetailScreenProps = {
  alertId: string;
};

// type RelatedSignal = {
//   title: string;
//   score: string;
//   riskLabel: string;
// };

type SourceRow = {
  type: string;
  label: string;
  href: string;
};

function getQueryErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    const e = error as HttpRequestError;
    if (typeof e.status === 'number') {
      return `The server returned an error (${e.status}). ${e.message}`;
    }
    return error.message;
  }
  return 'Unable to load alert detail. Please try again.';
}

function pickVictimCount(summary: string): string | null {
  const deathMatch = summary.match(/at least\s+(\d[\d,]*)\s+deaths?/i);
  if (deathMatch?.[1]) return deathMatch[1];
  const victimMatch = summary.match(/(\d[\d,]*)\+?\s+victims?/i);
  if (victimMatch?.[1]) return victimMatch[1];
  // return 'Not specified';
  return null;
}

function inferScopeFromTitle(title: string): string | null {
  if (/democratic republic of the congo|drc/i.test(title)) {
    return 'Democratic Republic of the Congo';
  }
  if (/\bu\.?s\.?\b|united states/i.test(title)) {
    return 'United States';
  }
  // return 'Not specified';
  return null;
}

function buildWhyThisMattersLines(data: AlertApiRecord): string[] {
  const items: string[] = [];
  const summary = data.summary?.trim();
  if (summary) {
    const end = summary.indexOf('. ');
    items.push(end > 0 ? summary.slice(0, end + 1).trim() : summary);
  }

  const entities = data.entities?.filter(
    (e): e is string => typeof e === 'string' && e.trim().length > 0
  );
  if (entities?.length) {
    const max = 5;
    const head = entities.slice(0, max).join(', ');
    items.push(
      entities.length > max
        ? `Named parties include ${head} and ${entities.length - max} others—useful for attribution, screening, and coordinated response.`
        : `Named parties include ${head}—useful for attribution, screening, and coordinated response.`
    );
  }

  const sec = data.secondary_category?.trim();
  if (sec) {
    items.push(
      `Secondary classification (${sec}) narrows how this signal is grouped with related cases and follow-up.`
    );
  } else if (data.category?.trim() && data.category.trim() !== 'Other') {
    items.push(
      `Filed under “${data.category.trim()}” so it can be compared with similar signals in your feed.`
    );
  }

  return items;
}

// function inferTrendLabel(riskLevel: string): string {
//   const risk = riskLevel.toUpperCase();
//   if (risk === 'HIGH') return 'Rising';
//   if (risk === 'MEDIUM') return 'Watch';
//   if (risk === 'LOW') return 'Stable';
//   return 'Unknown';
// }

// function buildRelatedSignals(): RelatedSignal[] {
//   return [
//     {
//       title: 'Crypto Romance Scams Targeting Older Adults',
//       score: '18',
//       riskLabel: 'HIGH',
//     },
//     {
//       title: 'AI-Generated Deepfake Investment Scams Rising',
//       score: '17',
//       riskLabel: 'HIGH',
//     },
//     {
//       title: 'Business Email Compromise Campaigns Increase',
//       score: '14',
//       riskLabel: 'MEDIUM',
//     },
//   ];
// }

// function RelatedCard({
//   title,
//   score,
//   riskLabel,
// }: {
//   title: string;
//   score: string;
//   riskLabel: string;
// }) {
//   const scoreClass =
//     riskLabel === 'HIGH'
//       ? 'text-danger'
//       : riskLabel === 'MEDIUM'
//         ? 'text-warning'
//         : 'text-success';
//
//   return (
//     <article className="border-border bg-surface/60 hover:border-primary-500/45 rounded-sm border p-4 transition-colors">
//       <RiskBadge label={riskLabel} className="mb-2 px-2 py-0.5" />
//       <h3 className="text-foreground line-clamp-2 text-[1.45rem] leading-tight font-semibold tracking-tight">
//         {title}
//       </h3>
//       <p className="mt-3 text-lg font-semibold">
//         <span className="text-body/85">Score </span>
//         <span className={scoreClass}>{score}</span>
//       </p>
//     </article>
//   );
// }

export function AlertDetailScreen({ alertId }: AlertDetailScreenProps) {
  const [fromRaw] = useQueryState('from');
  const alertsListHref = useMemo(
    () => alertsListHrefFromReturnParam(fromRaw ?? null),
    [fromRaw],
  );

  if (!alertId) {
    return (
      <EmptyState
        title="Alert not found"
        description="Missing alert identifier in the route."
      />
    );
  }

  const { data, isPending, isError, error, refetch } = useAlertDetailQuery(alertId);

  if (isPending) {
    return <LoadingState label="Loading alert detail…" />;
  }

  if (isError) {
    return (
      <ErrorState
        message={getQueryErrorMessage(error)}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!data) {
    return (
      <EmptyState
        title="Alert not found"
        description="This alert detail is not available right now."
      />
    );
  }

  const riskLabel = formatRiskLevelLabel(data.risk_level);
  const confidence = confidenceLabelFromRisk(riskLabel);
  const updatedAt = data.processed_at ?? data.published_at;
  const updatedLabel = updatedAt ? formatAlertDatePublished(updatedAt) : '—';
  const sourceLabel = data.source_name || 'Unknown';

  const sources: SourceRow[] = [
    {
      type: 'Primary Source',
      label: sourceLabel,
      href: data.source_url || '#',
    },
    // { type: 'Supporting Source', label: 'DOJ Press Release', href: '#' },
    // { type: 'Supporting Source', label: 'FTC Consumer Alert - Crypto Scams', href: '#' },
  ];

  // const timeline = [
  //   {
  //     period: data.published_at ? formatAlertDate(data.published_at).split(' — ')[0] : '—',
  //     event: data.title,
  //   },
  //   {
  //     period: data.processed_at ? formatAlertDate(data.processed_at).split(' — ')[0] : '—',
  //     event: 'Alert processed and published in intelligence feed',
  //   },
  //   { period: 'Ongoing', event: 'Monitoring continues as the situation develops' },
  // ];

  // const whyThisMatters = [
  //   `${riskLabel} risk signal with score ${data.signal_score ?? '—'} indicates elevated threat potential.`,
  //   `Category: ${data.category}${data.secondary_category ? ` / ${data.secondary_category}` : ''}.`,
  //   data.entities?.length
  //     ? `${data.entities.length} named entities identified in this alert.`
  //     : 'Entity-level attribution is not available in this alert.',
  // ];

  const victimCountLabel = pickVictimCount(data.summary);
  const geographicScope = inferScopeFromTitle(data.title);
  const affectedLabel = typeof data.affected === 'string' ? data.affected.trim() : '';
  const whyThisMattersLines = buildWhyThisMattersLines(data);

  // const relatedSignals = buildRelatedSignals();

  return (
    <div className="bg-background text-foreground min-h-screen px-6 py-8">
      <div className="mb-3">
        <Link
          href={alertsListHref}
          className="text-muted hover:text-foreground text-sm transition-colors"
        >
          ← Back to alerts
        </Link>
      </div>

      <header className="border-border bg-surface/55 mb-6 rounded-sm border px-5 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <RiskBadge label={riskLabel} className="px-2 py-1" />
            <h1 className="font-heading text-foreground mt-2 max-w-4xl text-2xl leading-tight font-semibold tracking-tight">
              {data.title}
            </h1>
          </div>

          <div className="shrink-0 text-right">
            <p className="text-muted text-xs font-semibold tracking-[0.12em] uppercase">
              Score
            </p>
            <p className="text-danger mt-1 text-5xl leading-none font-bold tabular-nums">
              {data.signal_score ?? '—'}
            </p>
          </div>
        </div>

        <div className="text-body/90 mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <span className="inline-flex items-center gap-2">
            <Eye className="text-success/90 size-4" aria-hidden="true" />
            Confidence: {confidence}
          </span>
          <span className="inline-flex items-center gap-2">
            <Newspaper className="text-info/90 size-4" aria-hidden="true" />
            Source: {sourceLabel}
          </span>
          <span className="inline-flex items-center gap-2">
            <Clock3 className="text-warning/90 size-4" aria-hidden="true" />
            Updated: {updatedLabel}
          </span>
          {/* <span className="inline-flex items-center gap-2">
            <Users className="text-body/80 size-4" aria-hidden="true" />
            Affected: Not specified
          </span> */}
          {affectedLabel ? (
            <span className="inline-flex items-center gap-2">
              <Users className="text-body/80 size-4" aria-hidden="true" />
              Affected: {affectedLabel}
            </span>
          ) : null}
        </div>
      </header>

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-2 text-sm font-semibold tracking-[0.12em] uppercase">
            Signal Summary
          </h2>
          <p className="text-body/95 text-[1.02rem] leading-relaxed">{data.summary}</p>
        </div>
      </section>

      {whyThisMattersLines.length > 0 ? (
        <section className="mb-6">
          <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
            <h2 className="text-muted mb-2 text-sm font-semibold tracking-[0.12em] uppercase">
              Why This Matters
            </h2>
            <ul className="space-y-2">
              {whyThisMattersLines.map((item, i) => (
                <li key={`why-${i}`} className="text-body/95 flex items-start gap-3 text-lg">
                  <span className="text-danger mt-1.5 text-sm leading-none">●</span>
                  <span className="text-base leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-3 text-sm font-semibold tracking-[0.12em] uppercase">
            Key Intelligence
          </h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {victimCountLabel != null ? (
              <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
                <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                  <Users className="text-info size-4" aria-hidden="true" />
                  Victims Identified
                </div>
                <p className="text-foreground mt-1 text-2xl leading-tight font-semibold tracking-tight">
                  {victimCountLabel}
                </p>
              </article>
            ) : null}
            {/* <article>...</article> always rendered pickVictimCount; displayed empty / Not specified when unmatched */}

            {geographicScope != null ? (
              <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
                <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                  <MapPinned className="text-success size-4" aria-hidden="true" />
                  Geographic Scope
                </div>
                <p className="text-success mt-1 text-2xl leading-tight font-semibold tracking-tight">
                  {geographicScope}
                </p>
              </article>
            ) : null}
            {/* inferScopeFromTitle(...) previously defaulted to Not specified */}

            {data.category?.trim() ? (
              <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
                <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                  <ShieldAlert className="text-warning size-4" aria-hidden="true" />
                  Fraud Type
                </div>
                <p className="text-foreground mt-1 text-2xl leading-tight font-semibold tracking-tight">
                  {data.category}
                  {/* data.category || 'Not specified' */}
                </p>
              </article>
            ) : null}

            {data.secondary_category?.trim() ? (
              <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
                <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                  <MessageSquare className="text-info size-4" aria-hidden="true" />
                  Primary Channels
                </div>
                <p className="text-info mt-1 text-2xl leading-tight font-semibold tracking-tight">
                  {data.secondary_category}
                  {/* secondary_category || 'Not specified' */}
                </p>
              </article>
            ) : null}

            {/* <article>Victim Awareness — Not specified (no field on AlertApiRecord yet)
              <UserX />
            </article> */}

            {/* Dummy trend label (inferTrendLabel(risk)); restore when API provides trend */}
            {/* <article className="border-border bg-surface/60 rounded-sm border px-4 py-3">
              <div className="text-body/90 inline-flex items-center gap-2 text-sm font-semibold">
                <TrendingUp className="text-danger size-4" aria-hidden="true" />
                Trend
              </div>
              <p className="text-foreground mt-1 text-2xl leading-tight font-semibold tracking-tight">
                {inferTrendLabel(riskLabel)}
              </p>
            </article> */}
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
              <p className="text-danger mt-1 text-4xl font-bold tracking-tight">
                {riskLabel}
              </p>
            </div>
            {/* <p className="text-body/95 text-[1.02rem] leading-relaxed">{data.summary}</p> */}
            <p className="text-body/95 text-[1.02rem] leading-relaxed line-clamp-2">
              {data.summary}
            </p>
          </div>
        </div>
      </section>

      {/* Dummy static actionable tips — restore when sourced from API
      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-3 text-sm font-semibold tracking-[0.12em] uppercase">
            Actionable Insight
          </h2>
          <div className="grid grid-cols-1 divide-y divide-border md:grid-cols-3 md:divide-x md:divide-y-0">
            <article className="px-4 py-3 text-center">
              <Shield className="text-success/90 mx-auto mb-2 size-7" aria-hidden="true" />
              <p className="text-body/95 text-[1.02rem] leading-snug">
                Avoid unsolicited offers related to this incident.
              </p>
            </article>
            <article className="px-4 py-3 text-center">
              <Search className="text-warning/90 mx-auto mb-2 size-7" aria-hidden="true" />
              <p className="text-body/95 text-[1.02rem] leading-snug">
                Verify claims and sources independently before acting.
              </p>
            </article>
            <article className="px-4 py-3 text-center">
              <TriangleAlert className="text-warning/90 mx-auto mb-2 size-7" aria-hidden="true" />
              <p className="text-body/95 text-[1.02rem] leading-snug">
                Escalate suspicious activity to trusted authorities immediately.
              </p>
            </article>
          </div>
        </div>
      </section>
      */}

      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-3 text-sm font-semibold tracking-[0.12em] uppercase">
            Sources
          </h2>
          <ul className="divide-border space-y-0 divide-y">
            {sources.map(source => (
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
                  target={source.href !== '#' ? '_blank' : undefined}
                  rel={source.href !== '#' ? 'noopener noreferrer' : undefined}
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

      {/* Timeline mixes API dates with placeholder events — uncomment `timeline` above when modeled in API
      <section className="mb-6">
        <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
          <h2 className="text-muted mb-3 text-sm font-semibold tracking-[0.12em] uppercase">
            Timeline
          </h2>
          <ul className="space-y-3">
            {timeline.map(item => (
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
      */}

      {/* Related Signals: no API data yet — restore when endpoint provides related alerts
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
            {relatedSignals.map(signal => (
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
      */}
    </div>
  );
}
