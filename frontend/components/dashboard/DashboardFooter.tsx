import { dashboardFooterContent as c } from '@/content/legal/dashboard-footer';
import Link from 'next/link';
import { type FC, Fragment } from 'react';

const companyEmphasisClass = 'text-foreground font-semibold';

const legalLinks = [
  { href: c.linkDisclaimerHref, label: c.linkDisclaimerLabel },
  { href: c.linkTermsHref, label: c.linkTermsLabel },
  { href: c.linkPrivacyHref, label: c.linkPrivacyLabel },
] as const;

const footerLinkClass =
  'text-muted-foreground hover:text-body underline decoration-transparent underline-offset-2 transition-[color,text-decoration-color] hover:decoration-body/40 focus-visible:text-body focus-visible:ring-primary-500 rounded-sm focus-visible:ring-2 focus-visible:outline-none';

const contactLinkClass =
  'text-body hover:text-foreground text-sm font-medium underline decoration-transparent underline-offset-2 transition-[color,text-decoration-color] hover:decoration-foreground/30 focus-visible:ring-primary-500 rounded-sm focus-visible:ring-2 focus-visible:outline-none';

export const DashboardFooter: FC = () => {
  return (
    <footer
      className="border-border-subtle bg-background-alt/40 text-muted-foreground shrink-0 border-t px-3 pt-6 pb-4 text-xs leading-relaxed sm:px-4 lg:px-6"
      aria-label="Disclosures"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:gap-8 lg:gap-10">
        <div className="text-muted-foreground/90 flex min-w-0 flex-col gap-1.5 text-pretty sm:max-w-md">
          <p>
            {c.productAttributionBefore}
            <strong className={companyEmphasisClass}>
              {c.productAttributionCompany}
            </strong>
          </p>
          <p>{c.descriptionLine1}</p>
          <p>{c.descriptionLine2}</p>
        </div>

        <div className="flex flex-col items-end gap-6 text-right sm:shrink-0">
          <nav
            className="flex flex-wrap justify-end gap-y-1"
            aria-label="Legal links"
          >
            {legalLinks.map((item, index) => (
              <Fragment key={item.href}>
                {index > 0 ? (
                  <span
                    aria-hidden
                    className="text-muted-foreground/40 px-2 text-[0.65rem] leading-none select-none"
                  >
                    ·
                  </span>
                ) : null}
                <Link href={item.href} className={footerLinkClass}>
                  {item.label}
                </Link>
              </Fragment>
            ))}
          </nav>

          <nav
            className="flex flex-col items-end gap-2 sm:gap-6"
            aria-label="Contact"
          >
            <div className="flex flex-col items-end">
              <span className="text-muted text-semibold text-sm">Support</span>
              <a
                href="mailto:support@covertlytics.com"
                className={contactLinkClass}
              >
                support@covertlytics.com
              </a>
            </div>
            <div className="flex flex-col items-end">
              <span className="text-muted text-semibold text-sm">Contact</span>
              <a
                href="mailto:contact@covertlytics.com"
                className={contactLinkClass}
              >
                contact@covertlytics.com
              </a>
            </div>
          </nav>
        </div>
      </div>
    </footer>
  );
};
