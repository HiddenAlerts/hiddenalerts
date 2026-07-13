'use client';

import {
  isSafeMailerLiteFormId,
  MAILERLITE_ACCOUNT_ID,
  MAILERLITE_EMBED_FORM_ID,
} from '@/data/mailerlite';
import { cn } from '@/lib/utils';
import { useEffect, useRef } from 'react';

import { ensureMailerLiteLoaded } from './MailerLiteUniversalScript';

type LandingMailerLiteFormProps = {
  /** Anchor target for header / in-page CTAs. */
  id?: string;
  className?: string;
  /** Accessible name for the signup region. */
  ariaLabel?: string;
};

/**
 * MailerLite embed mount. Re-creates the placeholder after mount so the
 * CDN script re-binds after HMR / soft navigation (otherwise first paint
 * can succeed and later visits show an empty box).
 */
export function LandingMailerLiteForm({
  id,
  className,
  ariaLabel = 'Join free intelligence updates',
}: LandingMailerLiteFormProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const formId = MAILERLITE_EMBED_FORM_ID;

  useEffect(() => {
    if (!isSafeMailerLiteFormId(formId)) return;

    const host = mountRef.current;
    if (!host) return;

    ensureMailerLiteLoaded();

    host.replaceChildren();
    const embed = document.createElement('div');
    embed.className = 'ml-embedded';
    embed.setAttribute('data-form', formId);
    host.appendChild(embed);

    // Nudge MailerLite to rescan after inserting the placeholder.
    window.ml?.('account', MAILERLITE_ACCOUNT_ID);
  }, [formId]);

  if (!isSafeMailerLiteFormId(formId)) {
    return null;
  }

  return (
    <div
      id={id}
      className={cn('scroll-mt-20 w-full min-w-0', className)}
      aria-label={ariaLabel}
    >
      <div ref={mountRef} />
    </div>
  );
}
