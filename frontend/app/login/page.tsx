'use client';

import { AuthFormShell } from '@/components/auth/AuthFormShell';
import { LandingFooter } from '@/components/landing/LandingFooter';
import { LandingHeader } from '@/components/landing/LandingHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAdminAuth } from '@/contexts/AdminAuthProvider';
import type { HttpRequestError } from '@/lib/api/client';
import { Lock, Mail } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState, type FormEvent } from 'react';
import { toast } from 'sonner';

type FieldErrors = {
  email?: string;
  password?: string;
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const DEFAULT_ADMIN_REDIRECT = '/admin/briefs';

function safeNextPath(next: string | null): string | null {
  if (!next) return null;
  // Only allow same-origin app paths, no protocol-relative or absolute URLs.
  if (!next.startsWith('/') || next.startsWith('//')) return null;
  return next;
}

function readErrorDetail(err: unknown): string | undefined {
  if (!err || typeof err !== 'object') return undefined;
  const body = (err as HttpRequestError).body;
  if (!body || typeof body !== 'object') return undefined;
  const detail = (body as { detail?: unknown }).detail;
  return typeof detail === 'string' ? detail : undefined;
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signIn, status } = useAdminAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  // If the user is already signed in (e.g. they typed `/login` while authed),
  // send them straight to the admin app.
  useEffect(() => {
    if (status !== 'authenticated') return;
    const next = safeNextPath(searchParams.get('next'));
    router.replace(next ?? DEFAULT_ADMIN_REDIRECT);
  }, [status, router, searchParams]);

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
    try {
      const user = await signIn(email.trim(), password);
      toast.success('Signed in.', {
        description: `Welcome back, ${user.full_name ?? user.email}.`,
      });
      const next = safeNextPath(searchParams.get('next'));
      router.replace(next ?? DEFAULT_ADMIN_REDIRECT);
    } catch (err) {
      const httpStatus = (err as HttpRequestError).status;
      const detail = readErrorDetail(err);
      if (httpStatus === 401 || httpStatus === 400) {
        toast.error('Invalid email or password.');
      } else if (detail) {
        toast.error(detail);
      } else {
        toast.error('Could not sign in. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
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
          if (errors.email) setErrors(prev => ({ ...prev, email: undefined }));
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
  );
}

export default function LoginPage() {
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
        <Suspense fallback={<div className="h-72" aria-hidden />}>
          <LoginForm />
        </Suspense>
      </AuthFormShell>
      <LandingFooter />
    </>
  );
}
