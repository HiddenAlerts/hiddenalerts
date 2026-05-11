import { cn } from '@/lib/utils';

const LOGO_SRC = '/images/logo.png';

type LandingLogoProps = {
  className?: string;
  iconClassName?: string;
  textClassName?: string;
  /** When true, appends ™ after the wordmark (e.g. footer attribution). */
  trademark?: boolean;
};

export function LandingLogo({
  className,
  iconClassName,
  textClassName,
  trademark = false,
}: LandingLogoProps) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <span
        className={cn(
          'inline-flex size-9 items-center justify-center overflow-hidden rounded-md p-0.5',
          iconClassName,
        )}
      >
        <img
          src={LOGO_SRC}
          alt=""
          width={36}
          height={36}
          className="size-full object-contain"
          decoding="async"
        />
      </span>
      <span
        className={cn(
          'font-heading text-foreground text-lg font-semibold tracking-tight',
          textClassName,
        )}
      >
        HiddenAlerts
        {trademark ? (
          <span className="align-super ml-0.5 text-[0.65em] font-normal leading-none">
            ™
          </span>
        ) : null}
      </span>
    </span>
  );
}
