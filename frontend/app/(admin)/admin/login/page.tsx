'use client';

import { AuthFormShell } from '@/components/auth/AuthFormShell';
import { LandingFooter } from '@/components/landing/LandingFooter';
import { LandingHeader } from '@/components/landing/LandingHeader';
import { LoadingState } from '@/components/ui/LoadingState';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAdminAuth } from '@/contexts/AdminAuthProvider';
import type { HttpRequestError } from '@/lib/api/client';
import { Lock, Mail } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { type FormEvent, Suspense, useEffect, useState } from 'react';
import { toast } from 'sonner';

type FieldErrors = {
  email?: string;
  password?: string;
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const DEFAULT_ADMIN_REDIRECT = '/admin/briefs';

function resolveAdminRedirect(next: string | null): string {
  if (!next?.startsWith('/') || next.startsWith('//')) {
    return DEFAULT_ADMIN_REDIRECT;
  }
  const pathOnly = next.split('?')[0] ?? next;
  if (pathOnly === '/admin/login') return DEFAULT_ADMIN_REDIRECT;
  if (pathOnly.startsWith('/admin')) return next;
  return DEFAULT_ADMIN_REDIRECT;
}

function readErrorDetail(err: unknown): string | undefined {
  if (!err || typeof err !== 'object') return undefined;
  const body = (err as HttpRequestError).body;
  if (!body || typeof body !== 'object') return undefined;
  const detail = (body as { detail?: unknown }).detail;
  return typeof detail === 'string' ? detail : undefined;
}

function isAdminAuthFailure(err: unknown): boolean {
  const status = (err as HttpRequestError).status;
  return status === 401 || status === 400;
}

function AdminLoginContent() {
  const searchParams = useSearchParams();
  const nextParam = searchParams.get('next');

  const { signIn, status } = useAdminAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  const checkingSession = status === 'loading';
  const alreadySignedIn = status === 'authenticated';

  useEffect(() => {
    if (status === 'authenticated') {
      window.location.replace(resolveAdminRedirect(nextParam));
    }
  }, [status, nextParam]);

  function validate(): FieldErrors {
    const next: FieldErrors = {};
    if (!email.trim()) {
      next.email = 'Email is required.';
    } else if (!EMAIL_RE.test(email.trim())) {
      next.email = 'Enter a valid email address.';
    }
    if (!password) {
      next.password = 'Password is required.';
    } else if (password.length < 8) {
      next.password = 'Password must be at least 8 characters.';
    }
    return next;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    const trimmedEmail = email.trim();

    try {
      const adminUser = await signIn(trimmedEmail, password);
      toast.success('Signed in.', {
        description: `Welcome back, ${adminUser.full_name ?? adminUser.email}.`,
      });
      window.location.replace(resolveAdminRedirect(nextParam));
    } catch (err) {
      if (isAdminAuthFailure(err)) {
        toast.error('Invalid email or password.');
      } else {
        const detail = readErrorDetail(err);
        toast.error(detail ?? 'Could not sign in. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (checkingSession || alreadySignedIn) {
    return (
      <>
        <LandingHeader showAuthActions={false} />
        <main className="flex flex-1 flex-col items-center justify-center px-4 py-16">
          <LoadingState
            label={alreadySignedIn ? 'Redirecting…' : 'Checking session…'}
          />
        </main>
        <LandingFooter />
      </>
    );
  }

  return (
    <>
      <LandingHeader showAuthActions={false} />
      <AuthFormShell
        title="Admin sign in"
        subtitle="Sign in with your HiddenAlerts admin credentials."
      >
        <form
          onSubmit={handleSubmit}
          noValidate
          className="flex flex-col gap-4"
        >
          <Input
            name="email"
            type="email"
            label="Email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={e => {
              setEmail(e.target.value);
              if (errors.email)
                setErrors(prev => ({ ...prev, email: undefined }));
            }}
            leftIcon={<Mail aria-hidden />}
            isError={Boolean(errors.email)}
            errorMessage={errors.email}
            required
          />

          <Input
            name="password"
            type="password"
            label="Password"
            autoComplete="current-password"
            placeholder="Enter your password"
            value={password}
            onChange={e => {
              setPassword(e.target.value);
              if (errors.password)
                setErrors(prev => ({ ...prev, password: undefined }));
            }}
            leftIcon={<Lock aria-hidden />}
            passwordWithIcon
            isError={Boolean(errors.password)}
            errorMessage={errors.password}
            required
          />

          <Button
            type="submit"
            size="md"
            loading={submitting}
            className="w-full"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </AuthFormShell>
      <LandingFooter />
    </>
  );
}

export default function AdminLoginPage() {
  return (
    <Suspense
      fallback={
        <>
          <LandingHeader showAuthActions={false} />
          <main className="flex flex-1 flex-col items-center justify-center px-4 py-16">
            <LoadingState label="Loading…" />
          </main>
          <LandingFooter />
        </>
      }
    >
      <AdminLoginContent />
    </Suspense>
  );
}
