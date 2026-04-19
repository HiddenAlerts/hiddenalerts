'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Mail } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

export function WaitlistForm() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) {
      toast.error('Enter your email to join the waitlist.');
      return;
    }
    if (!isValidEmail(trimmed)) {
      toast.error(
        'That email does not look valid. Please check and try again.',
      );
      return;
    }

    setLoading(true);
    try {
      const url = process.env.NEXT_PUBLIC_WAITLIST_API_URL?.trim();
      if (!url) {
        toast.info(
          'Waitlist signup is not live yet. Please check back soon.',
        );
        return;
      }

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: trimmed }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        error?: string;
      };

      if (!res.ok) {
        toast.error(data.error ?? 'Something went wrong. Please try again.');
        return;
      }

      toast.success('You are on the list. We will be in touch soon.');
      setEmail('');
    } catch {
      toast.error('Network error. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      id="waitlist"
      onSubmit={handleSubmit}
      className="mx-auto w-full max-w-md scroll-mt-24"
      noValidate
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          name="email"
          type="email"
          inputSize="md"
          placeholder="Enter your email"
          value={email}
          onChange={ev => setEmail(ev.target.value)}
          autoComplete="email"
          disabled={loading}
          leftIcon={<Mail className="size-4" aria-hidden />}
          parentStyles="w-full min-w-0 sm:flex-1"
          aria-label="Email address"
        />
        <Button
          type="submit"
          variant="default"
          size="md"
          loading={loading}
          className="h-11 shrink-0 py-0 sm:min-w-[160px]"
        >
          Get early access
        </Button>
      </div>
      <p className="text-muted-foreground mt-2 text-center text-xs sm:text-left">
        We only email about access and updates. Unsubscribe anytime.
      </p>
    </form>
  );
}
