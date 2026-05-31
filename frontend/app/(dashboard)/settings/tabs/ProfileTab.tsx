'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/AuthProvider';
import { getSupabaseClient } from '@/lib/supabase/client';
import { useEffect, useState, type FC, type FormEvent } from 'react';
import { toast } from 'sonner';

function readMetaName(meta: unknown): string {
  if (meta && typeof meta === 'object') {
    const value = (meta as Record<string, unknown>).full_name;
    if (typeof value === 'string') return value;
  }
  return '';
}

export const ProfileTab: FC = () => {
  const { user, subscriber } = useAuth();

  const initialName = readMetaName(user?.user_metadata);
  const email = subscriber?.email ?? user?.email ?? '';
  const accessLevel = subscriber?.access_level ?? 'subscriber';

  const [fullName, setFullName] = useState(initialName);
  const [submitting, setSubmitting] = useState(false);

  // Keep the form in sync if the auth context refreshes (e.g. after USER_UPDATED).
  useEffect(() => {
    setFullName(initialName);
  }, [initialName]);

  const trimmed = fullName.trim();
  const dirty = trimmed !== initialName.trim();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dirty || submitting) return;

    setSubmitting(true);
    try {
      const supabase = getSupabaseClient();
      const { error } = await supabase.auth.updateUser({
        data: { full_name: trimmed },
      });
      if (error) throw error;
      toast.success('Profile updated.');
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Could not update profile.';
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
          Profile information
        </h2>
        <p className="text-muted mt-1 text-sm">
          Update how your name appears in the app.
        </p>
      </div>

      <Input
        label="Full name"
        name="full_name"
        type="text"
        placeholder="Jane Doe"
        value={fullName}
        onChange={event => setFullName(event.target.value)}
        autoComplete="name"
      />

      <Input
        label="Email"
        name="email"
        type="email"
        value={email}
        disabled
        readOnly
      />

      <div className="space-y-1">
        <label className="text-muted text-xs font-medium">Account type</label>
        <div className="border-border bg-surface inline-flex items-center rounded-md border px-2.5 py-1 text-sm capitalize">
          {accessLevel}
        </div>
      </div>

      <div className="flex justify-end pt-1">
        <Button
          type="submit"
          variant="default"
          loading={submitting}
          disabled={!dirty}
        >
          Save changes
        </Button>
      </div>
    </form>
  );
};
