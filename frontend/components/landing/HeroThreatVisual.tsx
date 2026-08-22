import { cn } from '@/lib/utils';

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
    <div className="relative mx-auto aspect-square w-full max-w-[17.5rem] sm:max-w-xs lg:max-w-[20rem]" aria-hidden>
      <div className="bg-primary-500/20 absolute inset-[12%] rounded-full blur-3xl" />

      <svg
        viewBox="0 0 400 400"
        className="text-primary-500/35 relative size-full"
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

/** Hero globe visual — statistic card removed (hard-coded 247 was misleading). */
export function HeroThreatVisual({ className }: { className?: string }) {
  return (
    <div className={cn('relative w-full', className)}>
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-40"
        aria-hidden
        style={{
          backgroundImage:
            'radial-gradient(circle at 1px 1px, rgba(79,140,255,0.35) 1px, transparent 0)',
          backgroundSize: '18px 18px',
          maskImage:
            'radial-gradient(ellipse at center, black 35%, transparent 75%)',
        }}
      />
      <ThreatGlobe />
    </div>
  );
}
