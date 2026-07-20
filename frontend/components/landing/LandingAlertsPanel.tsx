'use client';

import {
  LANDING_ALERTS_LIMIT,
  fetchPublicAlerts,
  type PublicAlertListItem,
} from '@/lib/api/publicAlerts';
import {
  LIVE_ALERTS_PANEL,
  type LiveAlert,
  type RiskLevel,
} from '@/data/landing';
import { useEffect, useState } from 'react';

import { LandingLiveAlertRow } from './LandingLiveAlertRow';

type PanelMode = 'loading' | 'live' | 'empty';

/** Display the classification returned by the public alerts API. */
function mapRiskLevel(raw: string): RiskLevel {
  const level = raw.toLowerCase();
  if (level === 'critical') return 'CRITICAL';
  if (level === 'high') return 'HIGH';
  if (level === 'low') return 'LOW';
  return 'MEDIUM';
}

function categoryTone(category: string): LiveAlert['categoryTone'] {
  const lower = category.toLowerCase();
  if (
    lower.includes('cyber') ||
    lower.includes('crypto') ||
    lower.includes('emerging')
  ) {
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
    // Prefer risk_band when present; otherwise display risk_level as-is.
    level: mapRiskLevel(item.risk_band || item.risk_level),
    title: item.title,
    category: item.category,
    categoryTone: categoryTone(item.category),
    timestamp: formatTimestamp(item.source_published_at ?? item.published_at),
  };
}

/**
 * Left column — three most recent high-risk alerts (approved final mockup).
 * API-only: never pads with hardcoded sample alerts.
 */
export function LandingAlertsPanel() {
  const [mode, setMode] = useState<PanelMode>('loading');
  const [alerts, setAlerts] = useState<ReadonlyArray<LiveAlert>>([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
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
        // Network / API failure — show empty, never fake rows.
      }

      if (!cancelled) {
        setAlerts([]);
        setMode('empty');
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const panel = LIVE_ALERTS_PANEL;
  const showSkeleton = mode === 'loading';

  return (
    <div
      id="alerts"
      className="border-border bg-background-alt/80 flex h-full scroll-mt-24 flex-col rounded-xl border p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2
          id="alerts-heading"
          className="text-primary-500 text-[0.7rem] font-bold tracking-[0.16em] uppercase"
        >
          {panel.title}
        </h2>
        <span className="text-info text-[0.7rem] font-semibold tracking-wide">
          {panel.badge}
        </span>
      </div>

      <div className="mt-2 flex flex-1 flex-col">
        {showSkeleton ? (
          <div className="space-y-3 py-2" aria-busy="true" aria-label="Loading alerts">
            {Array.from({ length: LANDING_ALERTS_LIMIT }).map((_, i) => (
              <div
                key={i}
                className="border-border/50 flex items-start gap-3 border-b py-3.5 last:border-b-0"
              >
                <div className="bg-surface-muted size-11 shrink-0 animate-pulse rounded-full sm:size-12" />
                <div className="min-w-0 flex-1 space-y-2 pt-0.5">
                  <div className="bg-surface-muted h-3 w-[80%] animate-pulse rounded" />
                  <div className="bg-surface-muted h-2.5 w-1/2 animate-pulse rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : mode === 'empty' ? (
          <p className="text-muted flex flex-1 items-center py-8 text-sm leading-relaxed">
            High-risk alerts will appear here when available.
          </p>
        ) : (
          alerts.map((alert, i) => (
            <LandingLiveAlertRow key={`${alert.title}-${i}`} alert={alert} />
          ))
        )}
      </div>

      <div className="text-muted-foreground mt-auto border-border/50 border-t pt-3 text-xs leading-relaxed">
        <p>{panel.footnoteLead}</p>
        <p className="text-foreground mt-1.5 font-medium">{panel.footnoteCta}</p>
      </div>
    </div>
  );
}
