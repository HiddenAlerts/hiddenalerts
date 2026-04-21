import { Input } from '@/components/ui/input';
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Mail } from 'lucide-react';

const NEWSLETTER_URL = 'https://hiddenalerts.beehiiv.com';

type WaitlistFormProps = {
  formId?: string;
  microText: string;
};

export function WaitlistForm({ formId = 'waitlist', microText }: WaitlistFormProps) {

  return (
    <form
      id={formId}
      action={NEWSLETTER_URL}
      method="get"
      target="_blank"
      rel="noopener noreferrer"
      className="mx-auto w-full max-w-md scroll-mt-24"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          name="email"
          type="email"
          inputSize="md"
          placeholder="Enter your email"
          autoComplete="email"
          required
          leftIcon={<Mail className="size-4" aria-hidden />}
          parentStyles="w-full min-w-0 sm:flex-1"
          aria-label="Email address"
        />
        <button
          type="submit"
          className={cn(
            buttonVariants({ variant: 'default', size: 'md' }),
            'h-11 shrink-0 py-0 sm:min-w-[180px]',
          )}
        >
          Get Early Access
        </button>
      </div>
      <p className="text-muted-foreground mt-2 text-center text-xs sm:text-left">
        {microText}
      </p>
    </form>
  );
}
