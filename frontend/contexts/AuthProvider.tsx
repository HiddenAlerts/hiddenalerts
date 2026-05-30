'use client';

import type { HttpRequestError } from '@/lib/api/client';
import { fetchSubscriberMe } from '@/lib/api/subscriber';
import { getSupabaseClient } from '@/lib/supabase/client';
import type { SubscriberMeResponse } from '@/types/subscriber';
import type { Session, User } from '@supabase/supabase-js';
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

export type AuthContextValue = {
  status: AuthStatus;
  session: Session | null;
  user: User | null;
  /** Profile from our backend after Supabase login (optional until first fetch). */
  subscriber: SubscriberMeResponse | null;
  /** Supabase access token for backend API calls. */
  getAccessToken: () => string | null;
  signIn: (email: string, password: string) => Promise<void>;
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

  const applySession = useCallback(async (nextSession: Session | null) => {
    setSession(nextSession);
    setUser(nextSession?.user ?? null);

    if (!nextSession?.access_token) {
      setSubscriber(null);
      setStatus('unauthenticated');
      return;
    }

    try {
      const me = await fetchSubscriberMe(nextSession.access_token);
      setSubscriber(me);
      setStatus('authenticated');
    } catch (err) {
      const status = (err as HttpRequestError).status;
      if (status === 401) {
        const supabase = getSupabaseClient();
        await supabase.auth.signOut();
        setSession(null);
        setUser(null);
        setSubscriber(null);
        setStatus('unauthenticated');
        return;
      }
      // Network or temporary backend error — keep Supabase session.
      setSubscriber(null);
      setStatus('authenticated');
    }
  }, []);

  useEffect(() => {
    const supabase = getSupabaseClient();

    void supabase.auth.getSession().then(({ data }) => {
      void applySession(data.session);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      void applySession(nextSession);
    });

    return () => subscription.unsubscribe();
  }, [applySession]);

  const getAccessToken = useCallback(() => session?.access_token ?? null, [
    session,
  ]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const supabase = getSupabaseClient();
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) throw error;
      await applySession(data.session);
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
