"""Deterministic out-of-scope TOPIC-EXCLUSION veto (OPEN-5).

Defense-in-depth behind the AI relevance prompt (``ai_processor.py``). If an
alert's text clearly concerns an out-of-scope topic (terrorism, espionage, drug
trafficking, homicide, fugitive, gang, weapons, CSAM, political violence /
disinformation, …) AND carries no direct fraud / financial-crime signal, the
alert is routed to **review** (never auto-published) so an admin can decide.

It NEVER blocks a genuine fraud item: a direct fraud / financial-crime
"anti-veto" term in the article TEXT overrides the topic veto (e.g. "terrorism
financing via money laundering" stays publishable). The anti-veto deliberately
ignores ``matched_keywords`` (the keyword-filter's tags, which can be stale or
mis-tagged), and child-exploitation topics are absolute (never overridden) — both
guards added after a CSAM article (id 89) with a mis-tagged "crypto theft" keyword
evaded the veto. Because the veto only routes to *review* (not exclude), a false
positive is fully admin-recoverable, so the lexicon can lean toward catching
off-topic content.

Mirrors the M2 tiered pattern in ``source_rules.py`` and reuses its word-boundary
primitives (``_compile`` / ``_build_haystack`` / ``_matches_any``). The term lists
are the curated set from ``scripts/audit_offtopic_alerts.py``, with prefix terms
expanded to full word forms for word-boundary matching.
"""
from __future__ import annotations

from app.pipeline.publishing.source_rules import (
    _build_haystack,
    _compile,
    _matches_any,
)

# Out-of-scope topics — clear non-fraud subjects HiddenAlerts should not auto-publish.
_OUT_OF_SCOPE_TERMS: tuple[str, ...] = (
    # Exploitation / trafficking
    "child sexual abuse", "child sex", "csam", "child exploitation",
    "child abuse", "child pornography", "sex offender", "sex trafficking",
    "human trafficking",
    # Terrorism / extremism / national security
    "terrorism", "terrorist", "domestic terrorism", "violent extremism",
    "national security", "espionage", "spy ring", "coup attempt",
    "irgc", "islamic revolutionary guard", "hamas", "hezbollah", "isis",
    # Weapons / violence
    "weapons trafficking", "weapons charge", "explosives", "attack drones",
    "military contractor", "bombing", "shooting", "sniper", "school shooting",
    "armed robbery", "violent crime", "murder", "homicide", "kidnap",
    "hostage", "political violence",
    # Drugs / general crime. NOTE: bare "gang"/"gangs" is intentionally excluded —
    # it over-fires on in-scope fraud actors ("ransomware gang", "cybercrime gang",
    # "ShinyHunters gang"). Genuine street-gang violence is caught by the specific
    # phrasings below plus the violence terms (shooting/murder/violent crime).
    "drug trafficking", "narcotics trafficking", "narcotics conspiracy",
    "fugitive", "criminal gang", "street gang", "gang violence", "gang member",
    # Political / disinformation
    "disinformation", "election interference",
)

# Absolute out-of-scope: child sexual abuse / exploitation. These are NEVER
# overridden by a fraud anti-veto — there is no legitimate reason to auto-publish
# a CSAM story on a fraud feed, even if it carries an incidental financial term or
# a stale/mis-tagged fraud keyword (see the id-89 regression: a CSAM article whose
# matched_keywords were mis-tagged "crypto theft" suppressed the veto).
_ABSOLUTE_OUT_OF_SCOPE_TERMS: tuple[str, ...] = (
    "child sexual abuse", "child sex abuse", "child sex", "csam",
    "child exploitation", "child sexual exploitation", "child abuse",
    "child pornography", "sexual abuse material",
)

# If ANY of these clear fraud / financial-crime signals appears, do NOT veto —
# the alert has a financial mechanism even if an off-topic term also appears.
_ANTI_VETO_FRAUD_TERMS: tuple[str, ...] = (
    "fraud", "fraudulent", "scam", "laundering", "money laundering",
    "embezzle", "embezzled", "embezzlement", "embezzling", "bribery",
    "kickback", "ponzi", "pyramid scheme", "wire fraud", "mail fraud",
    "bank fraud", "investment fraud", "securities fraud", "tax evasion",
    "tax fraud", "identity theft", "credit card", "insider trading",
    "market manipulation", "phishing", "ransomware", "extortion",
    "racketeering", "rico", "fcpa", "foreign corrupt practices", "ofac",
    "sanctions", "illicit finance", "shell company", "false claims",
    "medicare fraud", "medicaid fraud", "healthcare fraud", "investor harm",
    "market abuse", "money mule", "stolen funds", "blocked entity",
    "blocked entities", "designated entity", "designated entities",
    "swindle", "swindled", "swindling", "skimming", "spoofing",
    "wash trading", "rug pull", "account takeover", "payment fraud",
)

_OUT_OF_SCOPE_PATTERNS = _compile(_OUT_OF_SCOPE_TERMS)
_ABSOLUTE_PATTERNS = _compile(_ABSOLUTE_OUT_OF_SCOPE_TERMS)
_ANTI_VETO_PATTERNS = _compile(_ANTI_VETO_FRAUD_TERMS)


def has_out_of_scope_topic(text: str) -> bool:
    return _matches_any(text, _OUT_OF_SCOPE_PATTERNS)


def has_absolute_out_of_scope_topic(text: str) -> bool:
    return _matches_any(text, _ABSOLUTE_PATTERNS)


def has_anti_veto_fraud_signal(text: str) -> bool:
    return _matches_any(text, _ANTI_VETO_PATTERNS)


def should_route_to_review_by_topic(
    *,
    title: str | None = None,
    summary: str | None = None,
    primary_category: str | None = None,
    matched_keywords=None,
) -> bool:
    """True if the alert should be routed to review on topic-scope grounds.

    Out-of-scope topic present AND no direct fraud / financial-crime anti-veto term
    in the article TEXT. Two refinements keep a stale/mis-tagged ``matched_keywords``
    tag from suppressing the veto (the id-89 CSAM regression):

    * The anti-veto runs over the article text only (title + summary + category),
      NOT ``matched_keywords`` — those are the keyword-filter's tags and can be
      stale or over-matched, so they must not cancel the veto on their own.
      Out-of-scope detection still uses the full haystack (keywords included), so
      the veto only gets harder to suppress, never easier.
    * Absolute out-of-scope topics (child sexual abuse / exploitation) are NEVER
      overridden by an anti-veto.

    Entity names are excluded from the haystack (reuses ``_build_haystack``) so a
    company/product name can't trip the veto.
    """
    full = _build_haystack(
        title=title,
        summary=summary,
        matched_keywords=matched_keywords,
        primary_category=primary_category,
    )
    if not full:
        return False
    # Absolute out-of-scope (CSAM / child exploitation): always route to review.
    if _matches_any(full, _ABSOLUTE_PATTERNS):
        return True
    if not _matches_any(full, _OUT_OF_SCOPE_PATTERNS):
        return False
    # Anti-veto considers the article TEXT only — never matched_keywords.
    text_only = _build_haystack(
        title=title,
        summary=summary,
        matched_keywords=None,
        primary_category=primary_category,
    )
    if _matches_any(text_only, _ANTI_VETO_PATTERNS):
        return False  # clear fraud / financial-crime signal in the text → never veto
    return True
