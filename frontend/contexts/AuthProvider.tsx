'use client';

import type { HttpRequestError } from '@/lib/api/client';
import { fetchSubscriberMe } from '@/lib/api/subscriber';
import { getSupabaseClient } from '@/lib/supabase/client';
import type { SubscriberMeResponse } from '@/types/subscriber';
import type { Session, User } from '@supabase/supabase-js';
import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

const SUPABASE_HASH_KEYS = [
  'access_token',
  'refresh_token',
  'provider_token',
  'provider_refresh_token',
  'expires_in',
  'expires_at',
  'token_type',
  'type',
  'error',
  'error_code',
  'error_description',
];

function replaceUrlWithoutHash() {
  const { pathname, search } = window.location;
  window.history.replaceState(null, '', `${pathname}${search}`);
}

/** Removes a lone trailing "#" (safe to call anytime). */
function stripEmptyLocationHash() {
  if (typeof window === 'undefined') return;
  const { hash } = window.location;
  if (!hash) return;
  const hashBody = hash.replace(/^#/, '').trim();
  if (!hashBody) replaceUrlWithoutHash();
}

/** Removes Supabase auth tokens from the hash (call after session is read). */
function stripSupabaseAuthHash() {
  if (typeof window === 'undefined') return;
  const { hash } = window.location;
  if (!hash) return;

  const hashBody = hash.replace(/^#/, '').trim();
  if (!hashBody) {
    replaceUrlWithoutHash();
    return;
  }

  const params = new URLSearchParams(hashBody);
  const hasAuthKey = SUPABASE_HASH_KEYS.some(key => params.has(key));
  if (hasAuthKey) replaceUrlWithoutHash();
}

export type AuthContextValue = {
  status: AuthStatus;
  session: Session | null;
  user: User | null;
  /** Profile from our backend after Supabase login (optional until first fetch). */
  subscriber: SubscriberMeResponse | null;
  /** Supabase access token for backend API calls. */
  getAccessToken: () => string | null;
  /**
   * Signs the user in via Supabase and refreshes `/subscriber/me`. Returns the
   * fresh subscriber profile (or `null` if the backend didn't respond), so the
   * caller can branch by `has_active_subscription` before navigating.
   */
  signIn: (
    email: string,
    password: string,
  ) => Promise<SubscriberMeResponse | null>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [subscriber, setSubscriber] = useState<SubscriberMeResponse | null>(
    null,
  );

  const applySession = useCallback(
    async (
      nextSession: Session | null,
    ): Promise<SubscriberMeResponse | null> => {
      setSession(nextSession);
      setUser(nextSession?.user ?? null);

      if (!nextSession?.access_token) {
        setSubscriber(null);
        setStatus('unauthenticated');
        return null;
      }

      try {
        const me = await fetchSubscriberMe(nextSession.access_token);
        setSubscriber(me);
        setStatus('authenticated');
        return me;
      } catch (err) {
        const status = (err as HttpRequestError).status;
        if (status === 401) {
          const supabase = getSupabaseClient();
          await supabase.auth.signOut();
          setSession(null);
          setUser(null);
          setSubscriber(null);
          setStatus('unauthenticated');
          return null;
        }
        // Network or temporary backend error — keep Supabase session.
        setSubscriber(null);
        setStatus('authenticated');
        return null;
      }
    },
    [],
  );

  function cleanupAuthUrl() {
    stripSupabaseAuthHash();
    // Supabase may clear token params but leave a bare "#" on the next tick.
    queueMicrotask(stripEmptyLocationHash);
  }

  useEffect(() => {
    const supabase = getSupabaseClient();

    void supabase.auth.getSession().then(({ data }) => {
      void applySession(data.session);
      cleanupAuthUrl();
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      void applySession(nextSession);
      cleanupAuthUrl();
    });

    return () => subscription.unsubscribe();
  }, [applySession]);

  const getAccessToken = useCallback(
    () => session?.access_token ?? null,
    [session],
  );

  const signIn = useCallback(
    async (email: string, password: string) => {
      const supabase = getSupabaseClient();
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) throw error;
      return applySession(data.session);
    },
    [applySession],
  );

  const signOut = useCallback(async () => {
    const supabase = getSupabaseClient();
    await supabase.auth.signOut();
    setSession(null);
    setUser(null);
    setSubscriber(null);
    setStatus('unauthenticated');
  }, []);

  return (
    <AuthContext.Provider
      value={{
        status,
        session,
        user,
        subscriber,
        getAccessToken,
        signIn,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}
