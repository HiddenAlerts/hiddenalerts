"""Deterministic out-of-scope TOPIC-EXCLUSION veto (OPEN-5).

Defense-in-depth behind the AI relevance prompt (``ai_processor.py``). If an
alert's text clearly concerns an out-of-scope topic (terrorism, espionage, drug
trafficking, homicide, fugitive, gang, weapons, CSAM, political violence /
disinformation, …) AND carries no direct fraud / financial-crime signal, the
alert is routed to **review** (never auto-published) so an admin can decide.

It NEVER blocks a genuine fraud item: a direct fraud / financial-crime
"anti-veto" term overrides the topic veto (e.g. "terrorism financing via money
laundering" stays publishable). Because the veto only routes to *review* (not
exclude), a false positive is fully admin-recoverable, so the lexicon can lean
toward catching off-topic content.

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
    # Drugs / general crime
    "drug trafficking", "narcotics trafficking", "narcotics conspiracy",
    "fugitive", "gang", "gangs", "criminal gang", "street gang",
    # Political / disinformation
    "disinformation", "election interference",
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
_ANTI_VETO_PATTERNS = _compile(_ANTI_VETO_FRAUD_TERMS)


def has_out_of_scope_topic(text: str) -> bool:
    return _matches_any(text, _OUT_OF_SCOPE_PATTERNS)


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

    Out-of-scope term present AND no direct fraud / financial-crime anti-veto term.
    Entity names are excluded from the haystack (reuses ``_build_haystack``) so a
    company/product name can't trip the veto.
    """
    text = _build_haystack(
        title=title,
        summary=summary,
        matched_keywords=matched_keywords,
        primary_category=primary_category,
    )
    if not text:
        return False
    if _matches_any(text, _ANTI_VETO_PATTERNS):
        return False  # clear fraud / financial-crime signal → never veto
    return _matches_any(text, _OUT_OF_SCOPE_PATTERNS)
