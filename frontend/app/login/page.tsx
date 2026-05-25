'use client';

import { AuthFormShell } from '@/components/auth/AuthFormShell';
import { LandingFooter } from '@/components/landing/LandingFooter';
import { LandingHeader } from '@/components/landing/LandingHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Lock, Mail } from 'lucide-react';
import Link from 'next/link';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';

type FieldErrors = {
  email?: string;
  password?: string;
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

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
      await new Promise(resolve => setTimeout(resolve, 600));
      toast.success('Signed in successfully.', {
        description: 'Welcome back to HiddenAlerts.',
      });
    } finally {
      setSubmitting(false);
    }
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
      </AuthFormShell>
      <LandingFooter />
    </>
  );
}
