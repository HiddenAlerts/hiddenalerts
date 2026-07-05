'use client';

import { fetchAdminMe, loginAdmin } from '@/lib/api/adminAuth';
import {
  clearAdminToken,
  getAdminToken,
  setAdminToken,
} from '@/lib/auth/adminSession';
import type { AdminUser } from '@/types/auth';
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';

type AdminAuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

export type AdminAuthContextValue = {
  status: AdminAuthStatus;
  user: AdminUser | null;
  /** Logs in via `/auth/login`, stores the token, and returns the user. */
  signIn: (email: string, password: string) => Promise<AdminUser>;
  /** Clears the stored token and local state. */
  signOut: () => void;
  /** Re-fetches `/auth/me` using the stored token. */
  refresh: () => Promise<void>;
};

const AdminAuthContext = createContext<AdminAuthContextValue | null>(null);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AdminAuthStatus>('loading');
  const [user, setUser] = useState<AdminUser | null>(null);

  const refresh = useCallback(async () => {
    const token = getAdminToken();
    if (!token) {
      setUser(null);
      setStatus('unauthenticated');
      return;
    }
    try {
      const me = await fetchAdminMe(token);
      setUser(me);
      setStatus('authenticated');
    } catch {
      // Token is invalid or expired — drop it and treat as logged out.
      clearAdminToken();
      setUser(null);
      setStatus('unauthenticated');
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await loginAdmin({ email, password });
    setAdminToken(res.access_token);
    setUser(res.user);
    setStatus('authenticated');
    return res.user;
  }, []);

  const signOut = useCallback(() => {
    clearAdminToken();
    setUser(null);
    setStatus('unauthenticated');
  }, []);

  return (
    <AdminAuthContext.Provider value={{ status, user, signIn, signOut, refresh }}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth(): AdminAuthContextValue {
  const ctx = useContext(AdminAuthContext);
  if (!ctx) {
    throw new Error('useAdminAuth must be used inside <AdminAuthProvider>');
  }
  return ctx;
}
