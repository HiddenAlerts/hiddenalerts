# Alert detail — deferred UI (archive)

Reference-only. **Not imported by the app.** Restore pieces into `AlertDetailScreen.tsx` when the API supports related alerts, timeline, actionable tips, extra sources, etc.

Captured from the pre-cleanup `AlertDetailScreen` (commented / placeholder blocks).

---

## Types & helpers (top of file, after imports)

```tsx
// type RelatedSignal = {
//   title: string;
//   score: string;
//   riskLabel: string;
// };

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
```

Uncomment and wire `RelatedSignal`; add **`TrendingUp`**, **`ArrowUpRight`** from `lucide-react` where needed below.

---

## Optional `pickVictimCount` / `inferScopeFromTitle` return defaults

```tsx
// return 'Not specified'; // (inside pickVictimCount / inferScopeFromTitle when no match)
```

---

## Extra `sources` rows (mock supporting sources)

```tsx
// { type: 'Supporting Source', label: 'DOJ Press Release', href: '#' },
// { type: 'Supporting Source', label: 'FTC Consumer Alert - Crypto Scams', href: '#' },
```

---

## `timeline` data (needs `formatAlertDate` imported from `@/lib/formatAlertDate`)

```tsx
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
```

---

## Alternate static `whyThisMatters` (replaces / supplements `buildWhyThisMattersLines`)

```tsx
// const whyThisMatters = [
//   `${riskLabel} risk signal with score ${data.signal_score ?? '—'} indicates elevated threat potential.`,
//   `Category: ${data.category}${data.secondary_category ? ` / ${data.secondary_category}` : ''}.`,
//   data.entities?.length
//     ? `${data.entities.length} named entities identified in this alert.`
//     : 'Entity-level attribution is not available in this alert.',
// ];
```

---

## After `whyThisMattersLines` — mock related list driver

```tsx
// const relatedSignals = buildRelatedSignals();
```

---

## Header: “Affected: Not specified” placeholder row

```tsx
{/* <span className="inline-flex items-center gap-2">
  <Users className="text-body/80 size-4" aria-hidden="true" />
  Affected: Not specified
</span> */}
```

---

## Key Intelligence — notes & trend card (`inferTrendLabel`, `TrendingUp`)

```tsx
{/* <article>...</article> always rendered pickVictimCount; displayed empty / Not specified when unmatched */}

{/* inferScopeFromTitle(...) previously defaulted to Not specified */}

{/* data.category || 'Not specified' */}

{/* secondary_category || 'Not specified' */}

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
```

---

## Risk Assessment — duplicate summary line (comment)

```tsx
{/* <p className="text-body/95 text-[1.02rem] leading-relaxed">{data.summary}</p> */}
```

---

## Actionable Insight section (needs `Shield`, `Search`, `TriangleAlert` from `lucide-react`)

```tsx
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
```

---

## Timeline section (uses `timeline` from above)

```tsx
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
```

---

## Related Signals section (`relatedSignals`, `RelatedCard`, `ArrowUpRight`)

```tsx
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
```
