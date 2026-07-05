import { TRUST_BAR } from '@/data/landing';

import { LandingIconBadge } from './LandingIconBadge';
import { LandingSection } from './LandingSection';

export function LandingTrustBar() {
  return (
    <LandingSection className="py-10 md:py-12">
      <p className="text-muted text-center text-sm sm:text-base">
        {TRUST_BAR.title}
      </p>
      <ul className="mt-8 flex flex-wrap items-center justify-center gap-8 sm:gap-12">
        {TRUST_BAR.items.map(item => (
          <li
            key={item.label}
            className="flex flex-col items-center gap-2 text-center"
          >
            <LandingIconBadge
              icon={item.icon}
              size="sm"
              className="border-transparent bg-transparent"
            />
            <span className="text-foreground text-sm font-medium">
              {item.label}
            </span>
          </li>
        ))}
      </ul>
    </LandingSection>
  );
}
