import { cn } from '@/lib/utils';

const LOGO_SRC = '/images/logo-symbol.png';

type LandingLogoProps = {
  className?: string;
  iconClassName?: string;
  textClassName?: string;
};

export function LandingLogo({
  className,
  iconClassName,
  textClassName,
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
      </span>
    </span>
  );
}
