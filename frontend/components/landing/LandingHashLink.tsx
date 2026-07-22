'use client';

import Link from 'next/link';
import type { ComponentProps, MouseEvent } from 'react';

type LandingHashLinkProps = ComponentProps<typeof Link>;

function hashFromHref(href: LandingHashLinkProps['href']): string | null {
  if (typeof href !== 'string') return null;
  const hashIndex = href.indexOf('#');
  if (hashIndex === -1) return null;
  const hash = href.slice(hashIndex + 1).trim();
  return hash || null;
}

function smoothScrollToId(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Same-page hash links with smooth scrolling. Native / Next.js hash jumps are
 * instant and ignore sticky-header `scroll-margin` inconsistently.
 */
export function LandingHashLink({
  href,
  onClick,
  ...props
}: LandingHashLinkProps) {
  const hash = hashFromHref(href);

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    if (event.defaultPrevented || !hash) return;

    const isSamePageHash =
      typeof href === 'string' &&
      (href.startsWith('#') || href.startsWith('/#'));

    if (!isSamePageHash) return;

    event.preventDefault();
    window.history.pushState(null, '', `#${hash}`);
    smoothScrollToId(hash);
  }

  return <Link href={href} onClick={handleClick} {...props} />;
}
