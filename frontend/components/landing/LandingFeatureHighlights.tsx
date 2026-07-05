import { FEATURE_HIGHLIGHTS } from '@/data/landing';

import { LandingIconBadge } from './LandingIconBadge';
import { LandingSection } from './LandingSection';

export function LandingFeatureHighlights() {
  return (
    <LandingSection className="py-10 md:py-12">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURE_HIGHLIGHTS.map(feature => (
          <article
            key={feature.title}
            className="border-border bg-surface/40 rounded-xl border p-5 sm:p-6"
          >
            <LandingIconBadge icon={feature.icon} />
            <h3 className="text-foreground mt-4 text-base font-semibold sm:text-lg">
              {feature.title}
            </h3>
            <p className="text-muted mt-2 text-sm leading-relaxed">
              {feature.description}
            </p>
          </article>
        ))}
      </div>
    </LandingSection>
  );
}
