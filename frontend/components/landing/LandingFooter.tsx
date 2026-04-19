import { LandingLogo } from './LandingLogo';

export function LandingFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-border-subtle bg-background mt-auto border-t px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 sm:flex-row sm:items-center">
        <div className="flex flex-col items-center gap-2 sm:items-start">
          <LandingLogo />
          <p className="text-muted-foreground text-center text-sm sm:text-left">
            © {year} HiddenAlerts
          </p>
        </div>

        {/* <nav className="flex items-center gap-6" aria-label="Footer">
          <Link
            href="/privacy"
            className="text-muted hover:text-body text-sm font-medium transition-colors"
          >
            Privacy
          </Link>
        </nav> */}
      </div>
    </footer>
  );
}
