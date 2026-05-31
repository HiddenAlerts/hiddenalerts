'use client';

import { useAuth } from '@/contexts/AuthProvider';
import { cn } from '@/lib/utils';
import { ChevronDown, LogOut } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, type FC } from 'react';

const ROLE_LABEL = 'Subscriber';

function deriveInitials(
  name: string | null | undefined,
  email: string | null | undefined,
): string {
  if (name && name.trim().length > 0) {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    if (parts.length === 1) {
      return parts[0][0]!.toUpperCase();
    }
  }
  return (email?.[0] ?? '?').toUpperCase();
}

function deriveDisplayName(
  name: string | null | undefined,
  email: string | null | undefined,
): string {
  if (name && name.trim().length > 0) return name.trim();
  if (!email) return 'Account';
  return email.split('@')[0] ?? email;
}

export const UserMenu: FC = () => {
  const { user, subscriber, signOut } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const metadataName = user?.user_metadata?.full_name;
  const fullName = typeof metadataName === 'string' ? metadataName : null;
  const email = subscriber?.email ?? user?.email ?? null;
  const initials = deriveInitials(fullName, email);
  const displayName = deriveDisplayName(fullName, email);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: MouseEvent | TouchEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  async function handleSignOut() {
    setOpen(false);
    await signOut();
    router.replace('/login');
  }

  if (!email) return null;

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className={cn(
          'hover:bg-surface inline-flex cursor-pointer items-center gap-2 rounded-md py-1 pr-1 pl-1 transition-colors sm:pr-2',
          open && 'bg-surface',
        )}
      >
        <span
          className="bg-primary-500/15 text-primary-300 flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold tracking-wide"
          aria-hidden
        >
          {initials}
        </span>
        <span className="hidden flex-col items-start leading-tight sm:flex">
          <span className="text-foreground max-w-[10rem] truncate text-sm font-medium">
            {displayName}
          </span>
          <span className="text-muted text-xs">{ROLE_LABEL}</span>
        </span>
        <ChevronDown
          className={cn(
            'text-muted hidden size-4 shrink-0 transition-transform duration-150 sm:block',
            open && 'rotate-180',
          )}
          aria-hidden
        />
      </button>

      {open ? (
        <div
          role="menu"
          className="border-border bg-background-alt absolute right-0 z-40 mt-2 w-60 overflow-hidden rounded-md border shadow-lg"
        >
          <div className="border-border border-b px-3 py-2.5">
            <p className="text-foreground truncate text-sm font-medium">
              {displayName}
            </p>
            <p className="text-muted truncate text-xs">{email}</p>
          </div>
          <div className="p-1">
            <button
              type="button"
              role="menuitem"
              onClick={handleSignOut}
              className="text-foreground hover:bg-surface flex w-full cursor-pointer items-center gap-2 rounded-sm px-2.5 py-2 text-sm transition-colors"
            >
              <LogOut className="text-muted size-4" aria-hidden />
              Sign out
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
};
