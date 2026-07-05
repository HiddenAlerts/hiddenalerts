import { cn } from '@/lib/utils';

import { THREAT_SIGNAL_STAT } from '@/data/landing';

/** Decorative hotspots scattered over the globe (percent coordinates). */
const HOTSPOTS = [
  { top: '24%', left: '38%', delay: '0s' },
  { top: '34%', left: '64%', delay: '0.6s' },
  { top: '52%', left: '30%', delay: '1.1s' },
  { top: '58%', left: '70%', delay: '0.3s' },
  { top: '44%', left: '50%', delay: '0.9s' },
  { top: '70%', left: '46%', delay: '1.4s' },
] as const;

function ThreatGlobe() {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-md" aria-hidden>
      {/* Ambient red glow */}
      <div className="bg-primary-500/25 absolute inset-[12%] rounded-full blur-3xl" />

      {/* Wireframe globe */}
      <svg
        viewBox="0 0 400 400"
        className="text-primary-500/40 relative size-full"
        fill="none"
      >
        <defs>
          <radialGradient id="globe-core" cx="50%" cy="42%" r="60%">
            <stop offset="0%" stopColor="rgb(238 68 66 / 0.35)" />
            <stop offset="55%" stopColor="rgb(238 68 66 / 0.08)" />
            <stop offset="100%" stopColor="rgb(238 68 66 / 0)" />
          </radialGradient>
        </defs>

        <circle cx="200" cy="200" r="150" fill="url(#globe-core)" />
        <circle
          cx="200"
          cy="200"
          r="150"
          stroke="currentColor"
          strokeWidth="1"
        />

        {/* Latitudes */}
        {[60, 110, 150, 110, 60].map((ry, i) => (
          <ellipse
            key={`lat-${i}`}
            cx="200"
            cy={80 + i * 60}
            rx="150"
            ry={ry / 4}
            stroke="currentColor"
            strokeWidth="0.75"
            opacity="0.55"
          />
        ))}

        {/* Longitudes */}
        {[150, 110, 60].map((rx, i) => (
          <ellipse
            key={`lon-${i}`}
            cx="200"
            cy="200"
            rx={rx}
            ry="150"
            stroke="currentColor"
            strokeWidth="0.75"
            opacity="0.55"
          />
        ))}
        <line
          x1="200"
          y1="50"
          x2="200"
          y2="350"
          stroke="currentColor"
          strokeWidth="0.75"
          opacity="0.55"
        />
      </svg>

      {/* Pulsing threat hotspots */}
      {HOTSPOTS.map((spot, i) => (
        <span
          key={i}
          className="absolute"
          style={{ top: spot.top, left: spot.left }}
        >
          <span
            className="bg-primary-400/60 absolute inline-flex size-2.5 animate-ping rounded-full"
            style={{ animationDelay: spot.delay }}
          />
          <span className="bg-primary-400 relative inline-flex size-2.5 rounded-full shadow-[0_0_10px_2px_rgb(238_68_66_/_0.6)]" />
        </span>
      ))}
    </div>
  );
}

/** Small upward-trending sparkline shown inside the live stat card. */
function StatSparkline({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 120 40"
      className={cn('text-primary-400 h-10 w-28', className)}
      fill="none"
      aria-hidden
    >
      <polyline
        points="0,34 14,28 26,30 40,20 54,24 68,12 82,18 96,8 110,12 120,4"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * Hero "active threat signals" visual: a stylised red wireframe globe with a
 * floating live-stat card. Purely presentational.
 */
export function HeroThreatVisual({ className }: { className?: string }) {
  return (
    <div className={cn('relative w-full', className)}>
      <ThreatGlobe />

      <div className="border-border bg-background-alt/85 shadow-lg sm:absolute sm:right-0 sm:bottom-0 mt-6 w-full rounded-xl border p-5 backdrop-blur sm:mt-0 sm:max-w-xs">
        <div className="flex items-center gap-2">
          <span className="bg-primary-500 inline-flex size-2.5 animate-pulse rounded-full" />
          <span className="text-primary-300 text-[0.7rem] font-semibold tracking-[0.14em] uppercase">
            {THREAT_SIGNAL_STAT.label}
          </span>
        </div>

        <div className="mt-3 flex items-end justify-between gap-3">
          <div>
            <p className="text-primary-500 font-heading text-5xl leading-none font-bold tracking-tight tabular-nums">
              {THREAT_SIGNAL_STAT.value}
            </p>
            <p className="text-foreground mt-2 text-sm font-medium">
              {THREAT_SIGNAL_STAT.headline}
            </p>
            <p className="text-muted text-xs">{THREAT_SIGNAL_STAT.detected}</p>
          </div>
          <StatSparkline />
        </div>

        <p className="text-muted-foreground mt-3 text-xs leading-relaxed">
          {THREAT_SIGNAL_STAT.caption}
        </p>
      </div>
    </div>
  );
}
