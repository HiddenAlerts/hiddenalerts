'use client';

import { useEffect } from 'react';

import {
  isAllowedMailerLiteScriptUrl,
  isSafeMailerLiteAccountId,
  MAILERLITE_ACCOUNT_ID,
  MAILERLITE_UNIVERSAL_SCRIPT_URL,
} from '@/data/mailerlite';

type MlQueueFn = {
  (...args: string[]): void;
  q?: string[][];
};

declare global {
  interface Window {
    ml?: MlQueueFn;
  }
}

const SCRIPT_DOM_ID = 'mailerlite-universal';

/**
 * Install MailerLite the official way:
 * 1) queue stub so `ml('account')` is safe before the CDN script loads
 * 2) load `universal.js` once from the allowlisted CDN URL
 * 3) bind account (safe to call again after HMR / soft navigation)
 */
export function ensureMailerLiteLoaded(): boolean {
  if (typeof window === 'undefined') return false;

  const scriptUrl = MAILERLITE_UNIVERSAL_SCRIPT_URL;
  const accountId = MAILERLITE_ACCOUNT_ID;

  if (
    !isAllowedMailerLiteScriptUrl(scriptUrl) ||
    !isSafeMailerLiteAccountId(accountId)
  ) {
    return false;
  }

  if (!window.ml) {
    const ml: MlQueueFn = (...args: string[]) => {
      (ml.q = ml.q || []).push(args);
    };
    ml.q = [];
    window.ml = ml;
  }

  window.ml('account', accountId);

  if (!document.getElementById(SCRIPT_DOM_ID)) {
    const script = document.createElement('script');
    script.id = SCRIPT_DOM_ID;
    script.src = scriptUrl;
    script.async = true;
    document.body.appendChild(script);
  }

  return true;
}

/** Landing-only bootstrap — keeps third-party JS off app/admin routes. */
export function MailerLiteUniversalScript() {
  useEffect(() => {
    ensureMailerLiteLoaded();
  }, []);

  return null;
}
