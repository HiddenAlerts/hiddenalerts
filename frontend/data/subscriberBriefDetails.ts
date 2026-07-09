import type { BriefDetail } from '@/types/briefs';

/**
 * Full reading content for each brief in `SUBSCRIBER_MOCK_BRIEFS`, keyed by
 * slug. Mock data only — pairs with the lighter `SubscriberBrief` shape used
 * by the library cards.
 */
const SUBSCRIBER_BRIEF_DETAILS: Record<string, BriefDetail> = {
  'prediction-markets-insider-threat': {
    id: 'brief-prediction-markets',
    slug: 'prediction-markets-insider-threat',
    title:
      'Prediction Markets Are Creating New Insider Threat and National Security Risks',
    category: 'Emerging Threats',
    coverTheme: 'emerging-threat',
    riskScore: 91,
    riskLevel: 'critical',
    confidenceLevel: 'high',
    primaryEntities: [
      'Prediction Market Platforms',
      'Corporate Insiders',
      'Government Employees',
    ],
    tags: ['Insider Threat', 'Market Manipulation', 'National Security'],
    executiveSummary:
      '<p>Rapidly growing prediction markets are creating financial incentives for insiders to leak sensitive information, introducing novel national security and insider-threat exposure that traditional compliance programs are not built to detect.</p>',
    whyThisMatters:
      '<p>Employees and officials with access to material non-public information now have a liquid, semi-anonymous venue to monetize it directly, without needing a traditional buyer for stolen data.</p>',
    keySignals:
      '<ul><li>Unusual trading volume on niche markets ahead of public announcements</li><li>Accounts funded via mixers or newly created wallets</li><li>Correlation between market moves and internal meeting schedules</li><li>Cross-posting of market links in closed employee forums</li></ul>',
    riskAssessment:
      '<p>Likelihood is rising as platform liquidity grows; impact is high where markets reference regulatory, M&A, or classified outcomes. Detection currently relies on after-the-fact correlation rather than real-time controls.</p>',
    whatOthersMiss:
      'Most coverage frames this as a gambling or fintech story. The overlooked angle is that these platforms function as an unregulated information marketplace — the trading activity itself is a leading indicator of a leak, often surfacing before any formal investigation begins.',
    implications:
      'Organizations should extend insider-threat monitoring to include public prediction-market activity correlated with employee access levels, and update NDAs/codes of conduct to explicitly cover market participation on covered topics.',
    mainBrief:
      '<p>Prediction markets have moved from niche curiosities to platforms with meaningful daily liquidity across political, corporate, and regulatory outcomes. This shift changes the incentive calculus for anyone with early access to material information.</p><p>Unlike traditional insider trading, which requires a security with a identifiable issuer and regulator, prediction market contracts on arbitrary events fall into a much greyer enforcement zone. Several recent cases have shown coordinated positioning shortly before public disclosures, with position sizes and timing that are difficult to explain as coincidence.</p><p>Security and compliance teams should treat this as a new insider-threat surface, not merely a market-integrity issue for the platforms themselves.</p>',
    supportingAlerts: [
      { url: '#', title: 'Public Report — FinCEN — Emerging Payment Risk Advisory 2026' },
      { url: '#', title: 'News Article — Reuters — Prediction Market Trading Surge' },
      { url: '#', title: 'Regulatory Filing — CFTC Enforcement Notice' },
      { url: '#', title: 'Academic Study — Market Microstructure and Information Leakage' },
      { url: '#', title: 'Company Filing — Platform Transparency Report Q1 2026' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-05-20',
  },

  'industrial-scale-scam-centers': {
    id: 'brief-industrial-scam-centers',
    slug: 'industrial-scale-scam-centers',
    title:
      'Industrial-Scale Scam Centers Continue Evolving into Transnational Criminal Enterprises',
    category: 'Organized Crime',
    coverTheme: 'organized-crime',
    riskScore: 93,
    riskLevel: 'critical',
    confidenceLevel: 'high',
    primaryEntities: ['Scam Compounds', 'Trafficking Networks', 'Shell Payment Processors'],
    tags: ['Organized Crime', 'Human Trafficking', 'Money Laundering'],
    executiveSummary:
      '<p>Scam compounds are professionalizing into transnational enterprises with corporate structures, recruitment pipelines, and layered money-laundering operations, operating with increasing impunity across multiple jurisdictions.</p>',
    whyThisMatters:
      '<p>These operations now generate billions in annual losses for victims worldwide while doubling as human-trafficking operations, creating both a financial crime and humanitarian crisis that spans borders.</p>',
    keySignals:
      '<ul><li>Recruitment ads disguised as legitimate remote job postings</li><li>Rapid incorporation and dissolution of shell payment processors</li><li>Victim funds routed through multiple crypto exchanges within hours</li><li>Coordinated messaging scripts reused across unrelated scam campaigns</li></ul>',
    riskAssessment:
      '<p>High and growing likelihood of exposure for financial institutions processing victim payments; reputational and regulatory impact is severe given the trafficking dimension.</p>',
    whatOthersMiss:
      'Coverage typically focuses on individual victim stories. The structural story — that these are run like corporations with HR, quotas, and performance reviews — is what makes them resilient to takedowns targeting individual compounds.',
    implications:
      'Financial institutions should treat scam-compound typologies as a distinct AML category with dedicated transaction-monitoring rules, and coordinate with law enforcement on victim-fund recovery windows.',
    mainBrief:
      '<p>What began as isolated scam operations in Southeast Asia has matured into a networked criminal industry with standardized playbooks, shared infrastructure, and cross-border logistics for both money and trafficked labor.</p><p>Compounds now specialize by scam type — romance fraud, crypto investment fraud, task-based scams — and share victim lead lists between operations. Payment flows are structured to minimize any single point of failure, with funds moving through multiple exchanges and shell entities before settling.</p><p>Enforcement actions against individual compounds have had limited lasting effect, as the underlying network reconstitutes quickly under new corporate shells.</p>',
    supportingAlerts: [
      { url: '#', title: 'Public Report — UNODC — Cyber Scam Report 2024' },
      { url: '#', title: 'News Article — Reuters — Transnational Scam Networks' },
      { url: '#', title: 'Company Filing — FinCEN SAR — 2026-1883' },
      { url: '#', title: 'NGO Report — Trafficking Recovery Coalition' },
      { url: '#', title: 'News Article — AP — Scam Compound Raids' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-05-20',
  },

  'nation-state-actors-blend-operations': {
    id: 'brief-nation-state-blend',
    slug: 'nation-state-actors-blend-operations',
    title:
      'Nation-State Actors Increasingly Blend Cyberattacks, Psychological Operations and Transnational Crime',
    category: 'National Security',
    coverTheme: 'national-security',
    riskScore: 91,
    riskLevel: 'critical',
    confidenceLevel: 'medium',
    primaryEntities: ['State-Aligned APT Groups', 'Criminal Proxies', 'Influence Networks'],
    tags: ['Nation-State Activity', 'Cyber Threats', 'Influence Operations'],
    executiveSummary:
      '<p>State-aligned actors are fusing cyber intrusions, influence operations, and criminal proxies, blurring the line between espionage and organized crime and complicating attribution and response.</p>',
    whyThisMatters:
      '<p>Organizations that view cyber, disinformation, and financial crime as separate risk categories will miss campaigns that intentionally span all three to achieve a single strategic objective.</p>',
    keySignals:
      '<ul><li>Ransomware infrastructure reused across financially- and politically-motivated intrusions</li><li>Coordinated social media amplification following breach disclosures</li><li>Criminal groups operating with apparent state protection or tasking</li><li>Shared tooling observed across previously unrelated threat clusters</li></ul>',
    riskAssessment:
      '<p>Impact is high for critical infrastructure and government-adjacent organizations; likelihood is increasing as the cost of maintaining deniable criminal proxies falls.</p>',
    whatOthersMiss:
      'Most threat intelligence still triages incidents into "criminal" or "state" buckets. The blended cases are undercounted because they get filed under whichever label matches the first indicator analysts see.',
    implications:
      'Threat-intel teams should track infrastructure and tooling overlap across nominally separate campaigns rather than relying solely on attribution labels to drive response prioritization.',
    mainBrief:
      '<p>The traditional separation between nation-state espionage, cybercrime, and influence operations is eroding. Several recent campaigns show the same infrastructure supporting financially-motivated ransomware, politically-timed leaks, and coordinated social media narratives.</p><p>This blending is likely deliberate: it provides plausible deniability and lets state sponsors outsource operational risk to criminal proxies while retaining strategic control over targeting and timing.</p><p>Defenders should prioritize infrastructure-level correlation over attribution-first triage, since the same toolset may serve multiple objectives simultaneously.</p>',
    supportingAlerts: [
      { url: '#', title: 'Government Advisory — CISA Joint Advisory' },
      { url: '#', title: 'Public Report — Mandiant Threat Intelligence' },
      { url: '#', title: 'News Article — Reuters — State-Aligned Cyber Campaign' },
      { url: '#', title: 'Academic Study — Hybrid Threats Research Center' },
      { url: '#', title: 'Company Filing — Incident Disclosure Report' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-05-20',
  },

  'criminal-groups-impersonate-it-staff': {
    id: 'brief-it-impersonation',
    slug: 'criminal-groups-impersonate-it-staff',
    title:
      'Criminal Groups Increasingly Impersonate Internal IT Staff to Bypass Security Controls',
    category: 'Cyber Threats',
    coverTheme: 'cyber',
    riskScore: 90,
    riskLevel: 'critical',
    confidenceLevel: 'high',
    primaryEntities: ['Help-Desk Impersonators', 'MFA Reset Fraud Rings', 'Enterprise IT Teams'],
    tags: ['Social Engineering', 'Identity Fraud', 'Corporate Infiltration'],
    executiveSummary:
      '<p>Attackers are posing as internal IT and help-desk staff to socially engineer employees, reset credentials, and bypass multi-factor authentication at scale, often with better internal knowledge than the employees they target.</p>',
    whyThisMatters:
      '<p>These attacks exploit trust in internal support channels rather than technical vulnerabilities, making traditional perimeter and endpoint defenses ineffective as a primary control.</p>',
    keySignals:
      '<ul><li>Spoofed internal phone numbers or Slack/Teams handles</li><li>Urgent MFA reset requests referencing real internal ticket numbers</li><li>Callers with accurate org-chart or project knowledge from prior breaches</li><li>Spike in help-desk password reset volume outside business hours</li></ul>',
    riskAssessment:
      '<p>High likelihood for large organizations with distributed help-desk operations; impact ranges from account takeover to full domain compromise when privileged accounts are targeted.</p>',
    whatOthersMiss:
      'The focus on MFA-bypass technique misses the root cause: attackers are pre-researching victims using data from prior, unrelated breaches to sound convincingly internal, which no MFA policy alone will stop.',
    implications:
      'Help-desk verification procedures should require an out-of-band callback to a known-good number rather than caller-provided context, and internal org-chart data should be treated as sensitive.',
    mainBrief:
      '<p>A wave of intrusions has traced back not to malware or exploited software, but to phone calls: attackers impersonating IT staff convince employees or help-desk agents to reset credentials or approve MFA prompts.</p><p>What distinguishes recent campaigns is the depth of pre-attack research — callers reference real employee names, recent projects, and internal terminology, likely sourced from previous breaches, LinkedIn, and leaked internal documents.</p><p>Because the attack targets a human process rather than a technical control, conventional security tooling has limited visibility until after credentials are already reset.</p>',
    supportingAlerts: [
      { url: '#', title: 'Government Advisory — FBI IC3 Alert' },
      { url: '#', title: 'Public Report — CrowdStrike Threat Report' },
      { url: '#', title: 'News Article — Bleeping Computer — Help Desk Social Engineering' },
      { url: '#', title: 'Company Filing — Breach Disclosure' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-05-17',
  },

  'fraud-corruption-government-innovation': {
    id: 'brief-government-innovation',
    slug: 'fraud-corruption-government-innovation',
    title:
      'Fraud and Corruption Risks Continue Targeting High-Value Government Innovation Programs',
    category: 'Government Corruption',
    coverTheme: 'corruption',
    riskScore: 89,
    riskLevel: 'critical',
    confidenceLevel: 'medium',
    primaryEntities: ['Shell Vendors', 'Grant Program Administrators', 'Procurement Officials'],
    tags: ['Government Corruption', 'Procurement Fraud', 'Shell Companies'],
    executiveSummary:
      '<p>Large government innovation and grant programs are being exploited through collusion, shell vendors, and procurement fraud, diverting funds intended for legitimate research and development.</p>',
    whyThisMatters:
      '<p>These programs are often fast-tracked with reduced oversight to encourage innovation, which is precisely the gap fraud schemes are designed to exploit.</p>',
    keySignals:
      '<ul><li>Newly formed vendors winning disproportionately large early-stage awards</li><li>Overlapping ownership between grant reviewers and awarded vendors</li><li>Deliverables that mirror boilerplate language across unrelated awards</li><li>Subcontracts routed back to entities tied to the prime awardee</li></ul>',
    riskAssessment:
      '<p>Impact is significant given program dollar values; likelihood increases wherever review timelines are compressed relative to award size.</p>',
    whatOthersMiss:
      'Audits typically sample large, established vendors. The actual exposure concentrates in newly formed entities that pass initial eligibility checks but lack any operating history to validate delivery capability.',
    implications:
      'Program administrators should weight vendor operating history and conflict-of-interest disclosures more heavily in award scoring, and require independent delivery verification before milestone payments.',
    mainBrief:
      '<p>Government innovation programs, designed to move quickly and take on early-stage risk, have become a recurring target for procurement fraud. The same features that make these programs attractive to legitimate innovators — reduced red tape, fast award cycles — also reduce the friction fraud schemes must overcome.</p><p>Recent cases show patterns of collusion between reviewers and applicant entities, shell vendors with no verifiable operating history, and subcontracting arrangements designed to obscure where funds ultimately land.</p><p>Strengthening vendor vetting without materially slowing award timelines is the central policy challenge going forward.</p>',
    supportingAlerts: [
      { url: '#', title: 'Government Advisory — Inspector General Report' },
      { url: '#', title: 'News Article — Reuters — Grant Fraud Investigation' },
      { url: '#', title: 'Public Report — GAO Procurement Risk Assessment' },
      { url: '#', title: 'Company Filing — Vendor Debarment Notice' },
      { url: '#', title: 'Academic Study — Public Procurement Integrity Review' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-05-15',
  },

  'organized-enrollment-fraud-networks': {
    id: 'brief-enrollment-fraud',
    slug: 'organized-enrollment-fraud-networks',
    title:
      'Organized Enrollment Fraud Networks Continue Exploiting Government Benefit Programs',
    category: 'Financial Crime',
    coverTheme: 'financial-crime',
    riskScore: 74,
    riskLevel: 'high',
    confidenceLevel: 'medium',
    primaryEntities: ['Benefit Program Administrators', 'Synthetic Identity Rings'],
    tags: ['Fraud', 'Identity Fraud', 'Government Benefits'],
    executiveSummary:
      '<p>Coordinated networks are mass-enrolling synthetic and stolen identities into benefit programs across multiple states, exploiting inconsistent identity-verification standards.</p>',
    whyThisMatters:
      '<p>Cross-state enrollment fraud is difficult to detect at the state level, since no single administrator sees the full pattern of a coordinated, multi-jurisdiction network.</p>',
    keySignals:
      '<ul><li>Clusters of enrollments sharing device fingerprints or IP ranges</li><li>Reused banking details across seemingly unrelated applicants</li><li>Enrollment velocity inconsistent with organic population growth</li><li>Documents that pass automated checks but fail manual review</li></ul>',
    riskAssessment:
      '<p>Moderate-to-high impact concentrated in programs with weaker identity-proofing; likelihood is elevated wherever enrollment is fully remote.</p>',
    whatOthersMiss:
      'State-level fraud units rarely share enrollment data in real time, so networks simply rotate targeted states faster than information-sharing agreements can catch up.',
    implications:
      'Cross-state data-sharing consortia and shared device/IP risk signals would materially reduce the window these networks currently exploit.',
    mainBrief:
      '<p>Benefit program fraud has shifted from opportunistic individual claims to organized, multi-state enrollment operations using synthetic and stolen identities at scale.</p><p>These networks exploit the fact that most program integrity controls operate within a single state or agency, with limited real-time visibility into enrollment patterns elsewhere. By rotating across jurisdictions, they stay ahead of any single administrator\'s fraud detection capacity.</p><p>Improved cross-jurisdiction data sharing, rather than stronger controls within any one program, is likely the highest-leverage intervention.</p>',
    supportingAlerts: [
      { url: '#', title: 'Government Advisory — OIG Fraud Alert' },
      { url: '#', title: 'News Article — AP — Benefit Fraud Ring' },
      { url: '#', title: 'Public Report — State Auditor Findings' },
      { url: '#', title: 'Company Filing — Program Integrity Report' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-05-12',
  },

  'federal-anti-fraud-infrastructure': {
    id: 'brief-antifraud-infrastructure',
    slug: 'federal-anti-fraud-infrastructure',
    title:
      'Federal Authorities Expand Anti-Fraud Infrastructure as Fraud Continues Scaling',
    category: 'National Security',
    coverTheme: 'national-security',
    riskScore: 87,
    riskLevel: 'critical',
    confidenceLevel: 'medium',
    primaryEntities: ['Federal Fraud Task Forces', 'Data-Sharing Consortia'],
    tags: ['Regulatory', 'Nation-State Activity', 'Fraud'],
    executiveSummary:
      '<p>Agencies are standing up new data-sharing and detection infrastructure as fraud losses outpace legacy controls, signaling a shift toward centralized, cross-agency fraud intelligence.</p>',
    whyThisMatters:
      '<p>Organizations that don\'t align their own fraud-reporting and data-sharing practices with these new federal frameworks risk being left with blind spots as adoption spreads.</p>',
    keySignals:
      '<ul><li>New interagency data-sharing agreements announced</li><li>Increased funding for centralized fraud-detection platforms</li><li>Pilot programs requiring real-time reporting from financial institutions</li><li>Expanded subpoena and information-request authority for fraud units</li></ul>',
    riskAssessment:
      '<p>Low direct risk to well-prepared institutions; moderate compliance burden as reporting requirements expand and timelines tighten.</p>',
    whatOthersMiss:
      'Coverage focuses on the funding announcements themselves. The more consequential detail is the specific data-sharing standards being adopted, which will determine integration cost for affected institutions.',
    implications:
      'Compliance and fraud teams should track emerging federal reporting standards now, ahead of mandatory adoption timelines, to avoid rushed integration work later.',
    mainBrief:
      '<p>As fraud losses continue to scale faster than individual institutions can counter alone, federal authorities are investing in shared infrastructure — centralized detection platforms, expanded data-sharing agreements, and faster interagency coordination.</p><p>This represents a structural shift from institution-by-institution fraud defense toward a networked model, similar to how anti-money-laundering information sharing evolved over the past two decades.</p><p>Early movers who align their internal fraud-data practices with the emerging standards will face a smoother transition than those who wait for mandatory compliance deadlines.</p>',
    supportingAlerts: [
      { url: '#', title: 'Government Advisory — Treasury Fraud Infrastructure Announcement' },
      { url: '#', title: 'News Article — Reuters — Federal Fraud Task Force Expansion' },
      { url: '#', title: 'Public Report — GAO Fraud Risk Assessment' },
      { url: '#', title: 'Company Filing — Industry Comment Letter' },
      { url: '#', title: 'Academic Study — Interagency Data Sharing Review' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-05-10',
  },

  'organized-identity-theft-networks': {
    id: 'brief-identity-theft-networks',
    slug: 'organized-identity-theft-networks',
    title:
      'Organized Identity Theft Networks Continue Scaling Multi-State Fraud Operations',
    category: 'Financial Crime',
    coverTheme: 'identity',
    riskScore: 86,
    riskLevel: 'critical',
    confidenceLevel: 'high',
    primaryEntities: ['Document Forgery Rings', 'Account Takeover Networks'],
    tags: ['Identity Fraud', 'Organized Crime', 'Financial Crime'],
    executiveSummary:
      '<p>Identity-theft rings are industrializing document forgery and account takeover to run multi-state fraud campaigns with production-line efficiency.</p>',
    whyThisMatters:
      '<p>The scale and consistency of forged documents now rival legitimate issuance quality, undermining identity verification as a standalone control.</p>',
    keySignals:
      '<ul><li>Forged documents passing standard optical verification checks</li><li>Rapid account creation followed by immediate high-value transactions</li><li>Reused device and browser fingerprints across victim accounts</li><li>Coordinated timing of takeover attempts across institutions</li></ul>',
    riskAssessment:
      '<p>High impact for financial institutions and identity-dependent services; likelihood continues rising alongside forged-document quality.</p>',
    whatOthersMiss:
      'Verification vendors benchmark forgery detection against last year\'s document quality. Current forgeries have closed that gap significantly, and detection rates quoted in vendor marketing often reflect stale test sets.',
    implications:
      'Institutions should supplement document verification with behavioral and device-based signals rather than relying on document authenticity checks alone.',
    mainBrief:
      '<p>Identity theft has moved well beyond opportunistic individual fraud into an industrialized operation with specialized roles: document forgers, account creators, and cash-out operators working in coordinated sequence across state lines.</p><p>The quality of forged identity documents has improved to the point that many pass standard automated verification, forcing a rethink of identity proofing as a single point of control.</p><p>Layering behavioral and device signals on top of document checks is increasingly necessary to catch what document verification alone now misses.</p>',
    supportingAlerts: [
      { url: '#', title: 'Government Advisory — FTC Identity Theft Report' },
      { url: '#', title: 'News Article — Reuters — Identity Fraud Ring Takedown' },
      { url: '#', title: 'Public Report — Identity Theft Resource Center' },
      { url: '#', title: 'Company Filing — Fraud Loss Disclosure' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-05-08',
  },

  'social-engineering-romance-fraud': {
    id: 'brief-romance-fraud',
    slug: 'social-engineering-romance-fraud',
    title:
      'Organized Social Engineering and Romance Fraud Schemes Continue Exploiting Elderly Victims',
    category: 'Fraud',
    coverTheme: 'fraud',
    riskScore: 78,
    riskLevel: 'high',
    confidenceLevel: 'medium',
    primaryEntities: ['Romance Fraud Networks', 'Money Mule Operators'],
    tags: ['Fraud', 'Social Engineering', 'Elder Fraud'],
    executiveSummary:
      '<p>Romance and trust-based fraud operations continue to target elderly victims with scripted, long-horizon social engineering campaigns designed to build trust over months before extracting funds.</p>',
    whyThisMatters:
      '<p>The extended relationship-building period makes these schemes resistant to point-in-time fraud warnings, since victims have already formed strong emotional trust before any transaction occurs.</p>',
    keySignals:
      '<ul><li>Gradual escalation from small to large fund transfers</li><li>Victim resistance to fraud warnings from family or institutions</li><li>Consistent scripted narratives across unrelated victim reports</li><li>Funds routed through money mules before reaching final destination</li></ul>',
    riskAssessment:
      '<p>Impact per victim is severe and often unrecoverable; likelihood is elevated for elderly populations with significant savings and limited digital literacy.</p>',
    whatOthersMiss:
      'Awareness campaigns focus on the initial contact red flags, but by the time large transfers occur, months of relationship-building have made victims actively resistant to intervention — the messaging needs to target the trust-building phase, not the transaction phase.',
    implications:
      'Financial institutions should train staff to recognize the behavioral signs of an active romance-fraud relationship, not just transaction anomalies, and design intervention scripts that account for victim resistance.',
    mainBrief:
      '<p>Romance fraud operations have refined their approach into a scripted, multi-month process: initial contact, relationship building, a fabricated crisis, and a request for funds — repeated with variations across thousands of victims simultaneously.</p><p>Because trust is built gradually and reinforced continuously, victims often actively defend the fraudster against warnings from banks or family members, having already invested significant emotional commitment.</p><p>Effective intervention requires recognizing the relationship-building phase itself, well before any request for money is made.</p>',
    supportingAlerts: [
      { url: '#', title: 'Government Advisory — FBI IC3 Elder Fraud Report' },
      { url: '#', title: 'News Article — AP — Romance Scam Network' },
      { url: '#', title: 'NGO Report — Elder Fraud Prevention Alliance' },
      { url: '#', title: 'Company Filing — Suspicious Activity Report Summary' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-05-05',
  },

  'caller-as-a-service-fraud': {
    id: 'brief-caller-as-a-service',
    slug: 'caller-as-a-service-fraud',
    title:
      'Caller-as-a-Service Fraud Expands as Organized Scam Networks Scale Corporate-Style Operations',
    category: 'Fraud',
    coverTheme: 'fraud',
    riskScore: 72,
    riskLevel: 'high',
    confidenceLevel: 'medium',
    primaryEntities: ['Call Centers', 'Telecom Providers', 'Financial Institutions'],
    tags: ['Phishing', 'Social Engineering', 'Telecom Fraud'],
    executiveSummary:
      '<p>Caller-as-a-Service platforms let fraud crews rent call-center capacity, spoofed numbers, and voice tooling on demand, lowering the barrier to running large-scale vishing campaigns.</p>',
    whyThisMatters:
      '<p>Renting rather than building fraud infrastructure means smaller, less sophisticated groups can now run campaigns previously only feasible for well-resourced operations.</p>',
    keySignals:
      '<ul><li>Pre-warmed phone numbers rotated across short campaign windows</li><li>Voice cloning used to impersonate known contacts</li><li>Rapid carrier-hopping to evade takedown requests</li><li>Shared scripts and call-center seats resold by the hour</li></ul>',
    riskAssessment:
      '<p>Impact concentrated in telecom and financial sectors with weak caller-authentication enforcement; likelihood is high and rising as the service model lowers entry costs for new fraud crews.</p>',
    whatOthersMiss:
      'The "as-a-service" business model itself is the story — takedowns targeting individual campaigns barely dent the underlying platform, which simply onboards a new set of customers.',
    implications:
      'Telecom providers and financial institutions should prioritize disrupting the platform layer (number pools, voice-cloning tooling) over chasing individual campaigns.',
    mainBrief:
      '<p>Caller-as-a-Service (CaaS) platforms have industrialized vishing fraud by offering pre-warmed phone numbers, voice-cloning kits, and rented call-center seats as an on-demand service, billed by the hour or per campaign.</p><p>This model means the underlying infrastructure survives even when individual fraud campaigns are disrupted — operators simply rotate carriers and numbers within minutes, and the platform continues serving other customers.</p><p>Institutions with weak STIR/SHAKEN enforcement or limited caller-authentication controls face the highest exposure as this model continues to scale.</p>',
    supportingAlerts: [
      { url: '#', title: 'Public Report — UNODC — Cyber Scam Report 2024' },
      { url: '#', title: 'News Article — Reuters — Transnational Scam Networks' },
      { url: '#', title: 'Company Filing — FinCEN SAR — 2026-1883' },
      { url: '#', title: 'News Article — Bleeping Computer — Vishing-as-a-Service' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-05-02',
  },

  'legacy-cryptocurrency-fraud': {
    id: 'brief-legacy-crypto-fraud',
    slug: 'legacy-cryptocurrency-fraud',
    title:
      'Legacy Cryptocurrency Fraud Continues Producing Long-Term Financial Recovery Challenges',
    category: 'Financial Crime',
    coverTheme: 'financial-crime',
    riskScore: 66,
    riskLevel: 'high',
    confidenceLevel: 'low',
    primaryEntities: ['Crypto Investment Platforms', 'Recovery Scam Operators'],
    tags: ['Financial Crime', 'Cryptocurrency', 'Fraud'],
    executiveSummary:
      '<p>Victims of legacy crypto schemes continue to face long, complex financial recovery and limited restitution pathways, with a growing secondary wave of "recovery scam" operators targeting the same victims again.</p>',
    whyThisMatters:
      '<p>The long tail of legacy crypto fraud creates a persistent victim population that remains vulnerable to follow-on scams promising fund recovery for an upfront fee.</p>',
    keySignals:
      '<ul><li>Unsolicited "recovery agent" outreach to prior fraud victims</li><li>Upfront fee requests for asset-recovery services</li><li>Reuse of original scam victim lists by unrelated operators</li><li>Limited or inconsistent restitution outcomes across jurisdictions</li></ul>',
    riskAssessment:
      '<p>Financial impact to individual victims is severe; systemic impact is moderate but persistent given the size of the historical victim pool.</p>',
    whatOthersMiss:
      'The recovery-scam wave is under-tracked because it targets a population already reluctant to report fraud a second time, making it one of the most underreported fraud categories.',
    implications:
      'Victim support organizations and institutions should proactively warn prior crypto-fraud victims about recovery scams rather than waiting for new complaints.',
    mainBrief:
      '<p>Years after the peak of several major cryptocurrency fraud schemes, victims continue to face limited and inconsistent paths to financial recovery, complicated by cross-border jurisdiction issues and the difficulty of tracing laundered crypto assets.</p><p>A secondary fraud wave has emerged targeting this same victim population: operators posing as asset-recovery specialists who charge upfront fees for recovery services that never materialize.</p><p>Because victims are often reluctant to report being defrauded twice, this secondary wave remains significantly underreported relative to its actual scale.</p>',
    supportingAlerts: [
      { url: '#', title: 'Government Advisory — SEC Investor Alert' },
      { url: '#', title: 'News Article — Reuters — Crypto Recovery Scams' },
      { url: '#', title: 'NGO Report — Fraud Victim Support Network' },
      { url: '#', title: 'Public Report — Chainalysis Crime Report' },
    ],
    featuredImage: undefined,
    status: 'published',
    publishedDate: '2026-04-28',
  },
};

export function findBriefDetailBySlug(slug: string): BriefDetail | undefined {
  return SUBSCRIBER_BRIEF_DETAILS[slug];
}
