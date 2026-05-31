'use client';

import { AuthFormShell } from '@/components/auth/AuthFormShell';
import { LandingFooter } from '@/components/landing/LandingFooter';
import { LandingHeader } from '@/components/landing/LandingHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getSupabaseClient } from '@/lib/supabase/client';
import { Lock, Mail, User } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';

type FieldErrors = {
  name?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [termsError, setTermsError] = useState<string | undefined>(undefined);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  function clearError(field: keyof FieldErrors) {
    setErrors(prev =>
      prev[field] === undefined ? prev : { ...prev, [field]: undefined },
    );
  }

  function validate(): { fields: FieldErrors; terms?: string } {
    const next: FieldErrors = {};
    if (!name.trim()) next.name = 'Name is required.';
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
    if (!confirmPassword) {
      next.confirmPassword = 'Confirm your password.';
    } else if (confirmPassword !== password) {
      next.confirmPassword = 'Passwords do not match.';
    }
    const terms = acceptTerms ? undefined : 'You must accept the terms.';
    return { fields: next, terms };
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const { fields, terms } = validate();
    setErrors(fields);
    setTermsError(terms);
    if (Object.keys(fields).length > 0 || terms) return;

    setSubmitting(true);
    try {
      const supabase = getSupabaseClient();
      const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: { full_name: name.trim() },
        },
      });

      if (error) {
        toast.error(error.message);
        return;
      }

      if (data.session) {
        toast.success('Account created.', {
          description: 'Pick a plan to get started.',
        });
        // New signups never have an active subscription — go to pricing.
        router.replace('/subscribe');
        return;
      }

      toast.success('Account created.', {
        description:
          'If email confirmation is enabled, check your inbox before signing in.',
      });
      router.replace('/login');
    } catch {
      toast.error('Could not create account. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <LandingHeader />
      <AuthFormShell
        title="Create your account"
        subtitle="Get early access to HiddenAlerts intelligence."
        footer={{
          prompt: 'Already have an account?',
          linkLabel: 'Sign in',
          href: '/login',
        }}
      >
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <Input
            name="name"
            type="text"
            label="Full name"
            autoComplete="name"
            placeholder="Jane Doe"
            value={name}
            onChange={e => {
              setName(e.target.value);
              clearError('name');
            }}
            leftIcon={<User aria-hidden />}
            isError={Boolean(errors.name)}
            errorMessage={errors.name}
            required
          />

          <Input
            name="email"
            type="email"
            label="Email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={e => {
              setEmail(e.target.value);
              clearError('email');
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
            autoComplete="new-password"
            placeholder="At least 8 characters"
            value={password}
            onChange={e => {
              setPassword(e.target.value);
              clearError('password');
            }}
            leftIcon={<Lock aria-hidden />}
            passwordWithIcon
            isError={Boolean(errors.password)}
            errorMessage={errors.password}
            required
          />

          <Input
            name="confirmPassword"
            type="password"
            label="Confirm password"
            autoComplete="new-password"
            placeholder="Re-enter your password"
            value={confirmPassword}
            onChange={e => {
              setConfirmPassword(e.target.value);
              clearError('confirmPassword');
            }}
            leftIcon={<Lock aria-hidden />}
            passwordWithIcon
            isError={Boolean(errors.confirmPassword)}
            errorMessage={errors.confirmPassword}
            required
          />

          <label className="text-muted mt-1 flex items-start gap-2 text-xs leading-relaxed">
            <input
              type="checkbox"
              checked={acceptTerms}
              onChange={e => {
                setAcceptTerms(e.target.checked);
                if (e.target.checked) setTermsError(undefined);
              }}
              className="border-border bg-surface accent-primary-500 focus:ring-primary-500/40 mt-0.5 size-4 shrink-0 cursor-pointer rounded-sm border focus:ring-2 focus:ring-offset-0"
            />
            <span>
              I agree to the{' '}
              <Link
                href="/terms"
                className="text-primary-500 hover:text-primary-400 underline-offset-2 hover:underline"
              >
                Terms
              </Link>{' '}
              and{' '}
              <Link
                href="/privacy"
                className="text-primary-500 hover:text-primary-400 underline-offset-2 hover:underline"
              >
                Privacy Policy
              </Link>
              .
            </span>
          </label>
          {termsError ? (
            <p className="text-danger-400 -mt-2 text-xs">{termsError}</p>
          ) : null}

          <Button
            type="submit"
            size="md"
            loading={submitting}
            className="mt-1 w-full"
          >
            {submitting ? 'Creating account…' : 'Create account'}
          </Button>
        </form>
      </AuthFormShell>
      <LandingFooter />
    </>
  );
}
