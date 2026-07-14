/**
 * Ken’s three sample Intelligence Briefs for the landing / CMS inventory.
 *
 * Landing UI: only brief #1 is shown as the Intelligence Brief Preview teaser
 * (Ken’s revised mockup — no full body, no thumbnail unless requested later).
 * Briefs #2 and #3 are catalogued here with Featured Image paths for CMS.
 */

export type SampleIntelligenceBrief = {
  id: string;
  title: string;
  category: string;
  riskScore: number;
  riskLevel: 'Critical';
  /** Public path under `public/images/briefs/`. */
  thumbnailSrc: string;
  /** When true, drives `INTELLIGENCE_BRIEF_PREVIEW` on the landing page. */
  showOnLandingPreview: boolean;
};

export const SAMPLE_INTELLIGENCE_BRIEFS: ReadonlyArray<SampleIntelligenceBrief> =
  [
    {
      id: 'account-takeover-economy',
      title:
        'The Account Takeover Economy: How Criminal Networks Are Targeting Mobile Banking',
      category: 'Financial Crime',
      riskScore: 80,
      riskLevel: 'Critical',
      thumbnailSrc: '/images/briefs/account-takeover-economy.png',
      showOnLandingPreview: true,
    },
    {
      id: 'cyber-warfare-evolves',
      title:
        'Cyber Warfare Evolves Into Influence, Intimidation, and Transnational Repression',
      category: 'Emerging Threat',
      riskScore: 91,
      riskLevel: 'Critical',
      thumbnailSrc: '/images/briefs/cyber-warfare-evolves.png',
      showOnLandingPreview: false,
    },
    {
      id: 'defense-innovation-programs',
      title:
        'Defense Innovation Programs Face Escalating Corruption and Procurement Fraud Risks',
      category: 'Government / Defense',
      riskScore: 84,
      riskLevel: 'Critical',
      thumbnailSrc: '/images/briefs/defense-innovation-programs.png',
      showOnLandingPreview: false,
    },
  ] as const;

export const LANDING_SAMPLE_BRIEF = SAMPLE_INTELLIGENCE_BRIEFS.find(
  brief => brief.showOnLandingPreview,
)!;

export const SAMPLE_BRIEF_THUMBNAILS = {
  accountTakeoverEconomy: '/images/briefs/account-takeover-economy.png',
  cyberWarfareEvolves: '/images/briefs/cyber-warfare-evolves.png',
  defenseInnovationPrograms: '/images/briefs/defense-innovation-programs.png',
} as const;
