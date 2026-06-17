'use client';

import { useSyncExternalStore } from 'react';

const QUERY = '(min-width: 768px)';

function subscribe(onStoreChange: () => void) {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener('change', onStoreChange);
  return () => mq.removeEventListener('change', onStoreChange);
}

function getSnapshot() {
  return window.matchMedia(QUERY).matches;
}

/** Server / SSR — desktop layout avoids missing search on first paint. */
function getServerSnapshot() {
  return true;
}

/** Whether viewport is at least Tailwind `md` (768px). */
export function useMinMd(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
