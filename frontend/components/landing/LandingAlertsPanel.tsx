'use client';

import {
  LANDING_ALERTS_LIMIT,
  fetchPublicAlerts,
  type PublicAlertListItem,
} from '@/lib/api/publicAlerts';
import {
  LIVE_ALERTS,
  LIVE_ALERTS_PANEL,
  SAMPLE_ALERTS_PANEL,
  type LiveAlert,
  type RiskLevel,
} from '@/data/landing';
import { useEffect, useState } from 'react';

import { LandingLiveAlertRow } from './LandingLiveAlertRow';

type PanelMode = 'loading' | 'live' | 'sample';

function mapRiskLevel(raw: string, score: number): RiskLevel {
  const level = raw.toLowerCase();
  if (level === 'critical' || score >= 85) return 'CRITICAL';
  if (level === 'high' || score >= 70) return 'HIGH';
  return 'MEDIUM';
}

function categoryTone(category: string): LiveAlert['categoryTone'] {
  const lower = category.toLowerCase();
  if (lower.includes('cyber') || lower.includes('crypto') || lower.includes('emerging')) {
    return 'info';
  }
  if (
    lower.includes('money') ||
    lower.includes('launder') ||
    lower.includes('government') ||
    lower.includes('defense')
  ) {
    return 'warning';
  }
  return 'danger';
}

function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function mapPublicAlert(item: PublicAlertListItem): LiveAlert {
  const score = Math.round(Number(item.signal_score) || 0);
  return {
    score,
    level: mapRiskLevel(item.risk_level, score),
    title: item.title,
    category: item.category,
    categoryTone: categoryTone(item.category),
    timestamp: formatTimestamp(item.source_published_at ?? item.published_at),
  };
}

/**
 * Landing alerts column.
 * Prefers public `GET /alerts?limit=5&risk_level=high`, then any published,
 * then clearly labeled sample rows — never leaves the card blank.
 */
export function LandingAlertsPanel() {
  const [mode, setMode] = useState<PanelMode>('loading');
  const [alerts, setAlerts] = useState<ReadonlyArray<LiveAlert>>(LIVE_ALERTS);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        // Prefer high-risk for the “Latest High-Risk Alerts” framing.
        let response = await fetchPublicAlerts({
          limit: LANDING_ALERTS_LIMIT,
          riskLevel: 'high',
        });
        let rows = (response.alerts ?? []).slice(0, LANDING_ALERTS_LIMIT);

        if (rows.length === 0) {
          response = await fetchPublicAlerts({ limit: LANDING_ALERTS_LIMIT });
          rows = (response.alerts ?? []).slice(0, LANDING_ALERTS_LIMIT);
        }

        if (cancelled) return;

        if (rows.length > 0) {
          setAlerts(rows.map(mapPublicAlert));
          setMode('live');
          return;
        }
      } catch {
        // Network / API failure — fall through to sample labeling.
      }

      if (!cancelled) {
        setAlerts(LIVE_ALERTS);
        setMode('sample');
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const panel = mode === 'live' ? LIVE_ALERTS_PANEL : SAMPLE_ALERTS_PANEL;
  const showSkeleton = mode === 'loading';
  const rows = showSkeleton ? LIVE_ALERTS : alerts;

  return (
    <div
      id="alerts"
      className="border-border bg-background-alt/80 flex min-h-[560px] scroll-mt-24 flex-col rounded-2xl border p-5 sm:min-h-[600px] sm:p-6 lg:min-h-[640px]"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2
          id="alerts-heading"
          className="text-primary-400 text-xs font-semibold tracking-[0.14em] uppercase"
        >
          {showSkeleton ? LIVE_ALERTS_PANEL.title : panel.title}
        </h2>
        <span className="text-info border-info/30 bg-info/10 rounded-full border px-2 py-0.5 text-[0.65rem] font-semibold tracking-wide">
          {showSkeleton ? LIVE_ALERTS_PANEL.badge : panel.badge}
        </span>
      </div>

      <div className="mt-2 flex flex-1 flex-col justify-center">
        {rows.map((alert, i) => (
          <LandingLiveAlertRow
            key={`${alert.title}-${i}`}
            alert={alert}
            className={showSkeleton ? 'opacity-60' : undefined}
          />
        ))}
      </div>

      <p className="text-muted-foreground mt-4 border-border/50 border-t pt-3 text-xs leading-relaxed">
        {showSkeleton ? LIVE_ALERTS_PANEL.footnote : panel.footnote}
      </p>
    </div>
  );
}
