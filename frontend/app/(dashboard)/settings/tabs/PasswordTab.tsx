'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getSupabaseClient } from '@/lib/supabase/client';
import { useState, type FC, type FormEvent } from 'react';
import { toast } from 'sonner';

const MIN_PASSWORD_LENGTH = 8;

export const PasswordTab: FC = () => {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function validate(): string | null {
    if (password.length < MIN_PASSWORD_LENGTH) {
      return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    if (password !== confirm) {
      return 'Passwords do not match.';
    }
    return null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;

    const validation = validate();
    if (validation) {
      setError(validation);
      return;
    }
    setError(null);

    setSubmitting(true);
    try {
      const supabase = getSupabaseClient();
      const { error: supabaseError } = await supabase.auth.updateUser({
        password,
      });
      if (supabaseError) throw supabaseError;
      toast.success('Password updated.');
      setPassword('');
      setConfirm('');
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Could not update password.';
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border-border bg-background-alt max-w-xl space-y-5 rounded-lg border p-5 sm:p-6"
    >
      <div>
        <h2 className="text-foreground text-base font-semibold">
          Change password
        </h2>
        <p className="text-muted mt-1 text-sm">
          Pick a new password — at least {MIN_PASSWORD_LENGTH} characters.
        </p>
      </div>

      <Input
        label="New password"
        name="new_password"
        type="password"
        passwordWithIcon
        value={password}
        onChange={event => setPassword(event.target.value)}
        autoComplete="new-password"
        required
      />

      <Input
        label="Confirm new password"
        name="confirm_password"
        type="password"
        passwordWithIcon
        value={confirm}
        onChange={event => setConfirm(event.target.value)}
        autoComplete="new-password"
        required
        isError={Boolean(error) && password !== confirm}
        errorMessage={password !== confirm ? error ?? undefined : undefined}
      />

      {error && password === confirm ? (
        <p className="text-danger-400 text-xs">{error}</p>
      ) : null}

      <div className="flex justify-end pt-1">
        <Button
          type="submit"
          variant="default"
          loading={submitting}
          disabled={!password || !confirm}
        >
          Update password
        </Button>
      </div>
    </form>
  );
};
