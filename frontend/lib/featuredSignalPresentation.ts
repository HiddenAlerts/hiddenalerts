import type { AlertItem } from '@/types/alert';

const EARLY_FRAMING_PREFIX =
  'Early-stage signal: this surfaced in source channels while details were still consolidating — ahead of typical headline pickup. ';

function hasEarlyFraming(text: string): boolean {
  return /early-stage signal/i.test(text);
}

/**
 * Featured-card-only copy: reframes agency-style “done deal” headlines toward
 * monitoring / pre-headline positioning without changing list rows or API data.
 */
export function presentFeaturedSignalCopy(alert: AlertItem): {
  title: string;
  description: string;
} {
  let title = alert.title.trim();
  let description = (alert.description ?? '').trim();
  const combined = `${title} ${description}`;

  const agencyContext =
    /\b(fbi|doj|sec|u\.s\. attorney|department of justice|fincen|ftc)\b/i.test(
      combined,
    );

  if (/\btakes action\b/i.test(title)) {
    title = title.replace(/\btakes action\b/gi, 'signals elevated activity');
  }
  if (/\bannounces\b/i.test(title)) {
    title = title.replace(/\bannounces\b/gi, 'surfaces');
  }

  const enforcementHeadlineTone =
    /\b(charg|indict|arrest|convict|sentenc|enforcement action|plead guilty|indictment)\b/i.test(
      title,
    );

  const postResolutionTone =
    /\b(sentenced to|years in prison|found guilty|pleaded guilty|was arrested|were arrested|indictment unsealed)\b/i.test(
      combined,
    );

  if (
    agencyContext &&
    (enforcementHeadlineTone || postResolutionTone) &&
    !hasEarlyFraming(description)
  ) {
    description = description
      ? `${EARLY_FRAMING_PREFIX}${description}`
      : `${EARLY_FRAMING_PREFIX}Use the source link for the full filing or release.`;
  }

  return { title, description };
}
