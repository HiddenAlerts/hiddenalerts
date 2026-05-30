'use client';

import { AuthFormShell } from '@/components/auth/AuthFormShell';
import { LandingFooter } from '@/components/landing/LandingFooter';
import { LandingHeader } from '@/components/landing/LandingHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { LoadingState } from '@/components/ui/LoadingState';
import { useAdminAuth } from '@/contexts/AdminAuthProvider';
import { useAuth } from '@/contexts/AuthProvider';
import type { HttpRequestError } from '@/lib/api/client';
import { Lock, Mail } from 'lucide-react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState, type FormEvent } from 'react';
import { toast } from 'sonner';

type FieldErrors = {
  email?: string;
  password?: string;
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const DEFAULT_ADMIN_REDIRECT = '/admin/briefs';
const DEFAULT_SUBSCRIBER_REDIRECT = '/dashboard';
const PAYWALL_REDIRECT = '/subscribe';

function resolveAdminRedirect(next: string | null): string {
  if (!next?.startsWith('/') || next.startsWith('//')) {
    return DEFAULT_ADMIN_REDIRECT;
  }
  const pathOnly = next.split('?')[0] ?? next;
  if (pathOnly === '/login' || pathOnly === '/signup') {
    return DEFAULT_ADMIN_REDIRECT;
  }
  if (pathOnly.startsWith('/admin')) return next;
  return DEFAULT_ADMIN_REDIRECT;
}

function resolveSubscriberRedirect(next: string | null): string {
  if (!next?.startsWith('/') || next.startsWith('//')) {
    return DEFAULT_SUBSCRIBER_REDIRECT;
  }
  const pathOnly = next.split('?')[0] ?? next;
  if (
    pathOnly === '/login' ||
    pathOnly === '/signup' ||
    pathOnly.startsWith('/admin')
  ) {
    return DEFAULT_SUBSCRIBER_REDIRECT;
  }
  return next;
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

function LoginPageContent() {
  const searchParams = useSearchParams();
  const nextParam = searchParams.get('next');

  const {
    signIn: signInAdmin,
    signOut: signOutAdmin,
    status: adminStatus,
  } = useAdminAuth();
  const {
    signIn: signInSubscriber,
    signOut: signOutSubscriber,
    status: subscriberStatus,
    subscriber,
  } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  const checkingSession =
    adminStatus === 'loading' || subscriberStatus === 'loading';
  const alreadySignedIn =
    adminStatus === 'authenticated' || subscriberStatus === 'authenticated';

  useEffect(() => {
    if (checkingSession) return;
    if (adminStatus === 'authenticated') {
      window.location.replace(resolveAdminRedirect(nextParam));
      return;
    }
    if (subscriberStatus === 'authenticated') {
      const target =
        subscriber?.has_active_subscription === false
          ? PAYWALL_REDIRECT
          : resolveSubscriberRedirect(nextParam);
      window.location.replace(target);
    }
  }, [
    checkingSession,
    adminStatus,
    subscriberStatus,
    subscriber,
    nextParam,
  ]);

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
      // 1) Try admin (backend JWT) — same credentials Ken provides for CMS.
      try {
        const adminUser = await signInAdmin(trimmedEmail, password);
        await signOutSubscriber();
        toast.success('Signed in.', {
          description: `Welcome back, ${adminUser.full_name ?? adminUser.email}.`,
        });
        window.location.replace(resolveAdminRedirect(nextParam));
        return;
      } catch (adminErr) {
        if (!isAdminAuthFailure(adminErr)) {
          const detail = readErrorDetail(adminErr);
          toast.error(detail ?? 'Could not sign in. Please try again.');
          return;
        }
      }

      // 2) Fall back to subscriber (Supabase).
      try {
        const me = await signInSubscriber(trimmedEmail, password);
        signOutAdmin();
        toast.success('Signed in.', {
          description: 'Welcome back to HiddenAlerts.',
        });
        const target =
          me?.has_active_subscription === false
            ? PAYWALL_REDIRECT
            : resolveSubscriberRedirect(nextParam);
        window.location.replace(target);
      } catch (subscriberErr) {
        const message =
          subscriberErr instanceof Error
            ? subscriberErr.message
            : 'Invalid email or password.';
        if (
          message.toLowerCase().includes('email not confirmed') ||
          message.toLowerCase().includes('confirm')
        ) {
          toast.error('Please confirm your email before signing in.');
        } else {
          toast.error('Invalid email or password.');
        }
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (checkingSession || alreadySignedIn) {
    return (
      <>
        <LandingHeader />
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
      <LandingHeader />
      <AuthFormShell
        title="Welcome back"
        subtitle="Sign in to continue to your HiddenAlerts dashboard."
        footer={{
          prompt: "Don't have an account?",
          linkLabel: 'Create one',
          href: '/signup',
        }}
      >
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
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

          <div className="-mt-1 flex justify-end">
            <Link
              href="#"
              className="text-muted hover:text-foreground focus-visible:ring-primary-500 rounded-sm text-xs underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:outline-none"
            >
              Forgot password?
            </Link>
          </div>

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

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <>
          <LandingHeader />
          <main className="flex flex-1 flex-col items-center justify-center px-4 py-16">
            <LoadingState label="Loading…" />
          </main>
          <LandingFooter />
        </>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
