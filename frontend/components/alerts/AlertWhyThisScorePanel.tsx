'use client';

import type { AlertRiskExplanation } from '@/types/alertsApi';

const FACTOR_LABELS: Record<keyof AlertRiskExplanation['factor_labels'], string> =
  {
    source_credibility: 'Source credibility',
    financial_impact: 'Financial impact',
    victim_scale: 'Victim scale',
    cross_source: 'Cross source',
    trend_acceleration: 'Trend acceleration',
  };

function formatRiskBandHeading(riskBand: string): string {
  const band = riskBand.trim().toLowerCase();
  if (band === 'critical') return 'Critical';
  if (band === 'high') return 'High';
  if (band === 'medium') return 'Medium';
  if (band === 'below_60') return 'Below 60';
  return riskBand.replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
}

export type AlertWhyThisScorePanelProps = {
  explanation: AlertRiskExplanation;
};

export function AlertWhyThisScorePanel({
  explanation,
}: AlertWhyThisScorePanelProps) {
  const factorEntries = Object.entries(explanation.factor_labels).filter(
    ([, value]) => typeof value === 'string' && value.trim().length > 0,
  ) as Array<[keyof AlertRiskExplanation['factor_labels'], string]>;

  return (
    <section className="mb-6">
      <div className="border-border bg-surface/55 rounded-sm border px-5 py-4">
        <h2 className="text-muted mb-2 text-sm font-semibold tracking-[0.12em] uppercase">
          Why This Score
        </h2>

        <div className="text-body/90 mb-4 flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <span>
            Score:{' '}
            <span className="text-foreground font-semibold tabular-nums">
              {explanation.score}
            </span>
          </span>
          <span>
            Risk band:{' '}
            <span className="text-foreground font-semibold">
              {formatRiskBandHeading(explanation.risk_band)}
            </span>
          </span>
          <span>
            Confidence:{' '}
            <span className="text-foreground font-semibold">
              {explanation.confidence}
            </span>
          </span>
        </div>

        {factorEntries.length > 0 ? (
          <div className="mb-4">
            <h3 className="text-muted mb-2 text-xs font-semibold tracking-[0.12em] uppercase">
              Factor labels
            </h3>
            <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {factorEntries.map(([key, value]) => (
                <li key={key} className="text-body/95 text-sm">
                  <span className="text-muted">{FACTOR_LABELS[key]}:</span>{' '}
                  <span className="font-medium">{value}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {explanation.primary_exposure.length > 0 ? (
          <div className="mb-4">
            <h3 className="text-muted mb-2 text-xs font-semibold tracking-[0.12em] uppercase">
              Primary exposure
            </h3>
            <ul className="flex flex-wrap gap-2">
              {explanation.primary_exposure.map(item => (
                <li
                  key={item}
                  className="bg-surface-muted text-body inline-flex rounded-md px-2.5 py-1 text-xs font-medium"
                >
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {explanation.reason_for_score.length > 0 ? (
          <div>
            <h3 className="text-muted mb-2 text-xs font-semibold tracking-[0.12em] uppercase">
              Reasons for score
            </h3>
            <ul className="space-y-2">
              {explanation.reason_for_score.map(reason => (
                <li
                  key={reason}
                  className="text-body/95 flex items-start gap-3 text-base"
                >
                  <span className="text-danger mt-1.5 text-sm leading-none">
                    ●
                  </span>
                  <span className="leading-relaxed">{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}
