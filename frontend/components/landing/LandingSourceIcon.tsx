import { cn } from '@/lib/utils';

import type { SourceIconVariant } from '@/data/landingSources';

type SourceIconProps = {
  variant: SourceIconVariant;
  className?: string;
};

const svgClass = (className?: string) => cn('size-10 shrink-0', className);

function SealIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={svgClass(className)} aria-hidden>
      <circle cx="20" cy="20" r="19" fill="none" stroke="currentColor" strokeWidth="1" />
      <circle cx="20" cy="20" r="14" fill="none" stroke="currentColor" strokeWidth="0.75" opacity="0.6" />
      <path
        d="M20 8l1.8 4.5 4.8.4-3.6 3.1 1.1 4.7L20 18.8l-4.1 2.9 1.1-4.7-3.6-3.1 4.8-.4L20 8z"
        fill="currentColor"
        opacity="0.85"
      />
      <circle cx="20" cy="20" r="3" fill="none" stroke="currentColor" strokeWidth="0.75" />
    </svg>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={svgClass(className)} aria-hidden>
      <path
        d="M20 4L8 9v11c0 7.2 5.1 13.9 12 15 6.9-1.1 12-7.8 12-15V9L20 4z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
      />
      <path
        d="M20 12v8M16 16h8"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.7"
      />
    </svg>
  );
}

/** IC3 — connected nodes / complaint network */
function NetworkIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={svgClass(className)} aria-hidden>
      <circle cx="20" cy="20" r="19" fill="none" stroke="currentColor" strokeWidth="1" />
      <circle cx="20" cy="14" r="3" fill="none" stroke="currentColor" strokeWidth="1.1" />
      <circle cx="12" cy="26" r="3" fill="none" stroke="currentColor" strokeWidth="1.1" />
      <circle cx="28" cy="26" r="3" fill="none" stroke="currentColor" strokeWidth="1.1" />
      <path
        d="M18 16.5L14 23.5M22 16.5l4 7M15 26h10"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.75"
      />
    </svg>
  );
}

/** FinCEN — classical building / treasury */
function BankIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={svgClass(className)} aria-hidden>
      <circle cx="20" cy="20" r="19" fill="none" stroke="currentColor" strokeWidth="1" />
      <path
        d="M12 28h16M13 28V18h14v10M20 12l10 6H10l10-6z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.15"
        strokeLinejoin="round"
      />
      <path
        d="M16 22v6M20 22v6M24 22v6"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.75"
      />
    </svg>
  );
}

/** SEC — balanced scales of justice / markets */
function ScalesIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={svgClass(className)} aria-hidden>
      <circle cx="20" cy="20" r="19" fill="none" stroke="currentColor" strokeWidth="1" />
      <path
        d="M20 10v18M14 28h12"
        stroke="currentColor"
        strokeWidth="1.15"
        strokeLinecap="round"
      />
      <path
        d="M12 14h16M12 14l-3 7a4 4 0 0 0 8 0l-3-7M28 14l-3 7a4 4 0 0 0 8 0l-3-7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** CISA — shield with lock / cyber defense */
function CyberIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={svgClass(className)} aria-hidden>
      <circle cx="20" cy="20" r="19" fill="none" stroke="currentColor" strokeWidth="1" />
      <path
        d="M20 9L11 13v7.5c0 5.5 4 10.5 9 11.5 5-1 9-6 9-11.5V13L20 9z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.15"
        strokeLinejoin="round"
      />
      <rect
        x="16.5"
        y="17"
        width="7"
        height="6"
        rx="1"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
      />
      <path
        d="M18 17v-1.5a2 2 0 0 1 4 0V17"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Krebs — press / document mark */
function PressIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={svgClass(className)} aria-hidden>
      <circle cx="20" cy="20" r="19" fill="none" stroke="currentColor" strokeWidth="1" />
      <rect
        x="12"
        y="11"
        width="16"
        height="18"
        rx="1.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.15"
      />
      <path
        d="M15.5 16h9M15.5 20h9M15.5 24h6"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.8"
      />
    </svg>
  );
}

/** BleepingComputer — monitor / tech */
function TechIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={svgClass(className)} aria-hidden>
      <circle cx="20" cy="20" r="19" fill="none" stroke="currentColor" strokeWidth="1" />
      <rect
        x="11"
        y="12"
        width="18"
        height="12"
        rx="1.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.15"
      />
      <path
        d="M16 28h8M20 24v4"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
      />
      <circle cx="20" cy="18" r="1.5" fill="currentColor" opacity="0.7" />
    </svg>
  );
}

export function SourceIcon({ variant, className }: SourceIconProps) {
  switch (variant) {
    case 'seal':
      return <SealIcon className={className} />;
    case 'shield':
      return <ShieldIcon className={className} />;
    case 'network':
      return <NetworkIcon className={className} />;
    case 'bank':
      return <BankIcon className={className} />;
    case 'scales':
      return <ScalesIcon className={className} />;
    case 'cyber':
      return <CyberIcon className={className} />;
    case 'press':
      return <PressIcon className={className} />;
    case 'tech':
      return <TechIcon className={className} />;
    default:
      return null;
  }
}
