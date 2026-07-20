import { keySignalsHtmlToArray } from '@/lib/keySignalsFormat';
import { stripHtmlToText } from '@/lib/htmlText';
import type { AdminBrief } from '@/types/admin';
import type {
  BriefWritePayload,
  CreateBriefPayload,
  UpdateBriefPayload,
} from '@/types/adminBriefsApi';

/**
 * TipTap empty docs are usually `<p></p>` / `<p><br></p>` — truthy strings that
 * must NOT overwrite real DB content on update.
 */
export function richTextOrOmit(html: string | undefined): string | undefined {
  if (!html) return undefined;
  return stripHtmlToText(html) ? html : undefined;
}

/**
 * Build the shared write shape. Callers decide create vs update semantics.
 *
 * Update rule (critical): omit empty wipe-sensitive fields so a partial PUT
 * with `exclude_unset=True` cannot clear Key Signals, entities, tags, or
 * rich text when the editor looks empty or conversion yields [].
 */
export function buildAdminBriefWritePayload(
  brief: AdminBrief,
  mode: 'create' | 'update',
): BriefWritePayload {
  const keySignals = keySignalsHtmlToArray(brief.keySignals);
  const supportingAlerts = brief.supportingAlerts
    .filter(a => a.url.trim())
    .map(a => ({
      url: a.url.trim(),
      title: a.title?.trim() || undefined,
    }));

  const payload: BriefWritePayload = {
    title: brief.title,
    slug: brief.slug || undefined,
    category: brief.category || undefined,
    risk_score: brief.riskScore,
    risk_level: brief.riskLevel,
    time_horizon: brief.timeHorizon,
    confidence_level: brief.confidenceLevel,
    brief_type: 'intelligence_brief',
    is_premium: brief.isPremium,
    supporting_alerts: supportingAlerts,
  };

  if (mode === 'create') {
    payload.primary_entities = brief.primaryEntities;
    payload.tags = brief.tags;
    payload.key_signals = keySignals;
    payload.executive_summary = richTextOrOmit(brief.executiveSummary);
    payload.why_this_matters = richTextOrOmit(brief.whyThisMatters);
    payload.risk_assessment = richTextOrOmit(brief.riskAssessment);
    payload.what_others_miss = richTextOrOmit(brief.whatOthersMiss);
    payload.implications = richTextOrOmit(brief.implications);
    payload.main_intelligence_brief = richTextOrOmit(brief.mainBrief);
    payload.analyst_notes = richTextOrOmit(brief.analystNotes);
    return payload;
  }

  // --- update: never send empty wipe-sensitive fields ---
  if (brief.primaryEntities.length > 0) {
    payload.primary_entities = brief.primaryEntities;
  }
  if (brief.tags.length > 0) {
    payload.tags = brief.tags;
  }
  if (keySignals.length > 0) {
    payload.key_signals = keySignals;
  }

  const executiveSummary = richTextOrOmit(brief.executiveSummary);
  if (executiveSummary !== undefined) {
    payload.executive_summary = executiveSummary;
  }
  const whyThisMatters = richTextOrOmit(brief.whyThisMatters);
  if (whyThisMatters !== undefined) {
    payload.why_this_matters = whyThisMatters;
  }
  const riskAssessment = richTextOrOmit(brief.riskAssessment);
  if (riskAssessment !== undefined) {
    payload.risk_assessment = riskAssessment;
  }
  const whatOthersMiss = richTextOrOmit(brief.whatOthersMiss);
  if (whatOthersMiss !== undefined) {
    payload.what_others_miss = whatOthersMiss;
  }
  const implications = richTextOrOmit(brief.implications);
  if (implications !== undefined) {
    payload.implications = implications;
  }
  const mainBrief = richTextOrOmit(brief.mainBrief);
  if (mainBrief !== undefined) {
    payload.main_intelligence_brief = mainBrief;
  }
  const analystNotes = richTextOrOmit(brief.analystNotes);
  if (analystNotes !== undefined) {
    payload.analyst_notes = analystNotes;
  }

  return payload;
}

export function mapAdminBriefToCreatePayload(brief: AdminBrief): CreateBriefPayload {
  return {
    ...buildAdminBriefWritePayload(brief, 'create'),
    title: brief.title,
  };
}

export function mapAdminBriefToUpdatePayload(brief: AdminBrief): UpdateBriefPayload {
  return buildAdminBriefWritePayload(brief, 'update');
}
