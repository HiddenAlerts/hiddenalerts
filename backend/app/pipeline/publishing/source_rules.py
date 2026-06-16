"""V1 source-specific publishing rules (Slice 3 — pure, deterministic, no DB).

Adds the source-aware layer on top of the Slice 2 generic policy:

  * KrebsOnSecurity is treated as **effective credibility 4** for V1 decisions
    (a runtime decision only — the ``sources`` table is NOT mutated).
  * BleepingComputer is **not** promoted. It is review-first by default and only
    *conditionally eligible* when the alert text clearly carries a financial /
    fraud signal (phishing, account takeover, ransomware+extortion, crypto theft,
    payment fraud, significant data-breach exposure, …). Generic vuln / patch /
    product-update / PoC / research items stay review-first.
  * All other sources have no special rule (effective credibility = stored).

Everything here is pure and side-effect free, and nothing is wired into the
live pipeline yet (Slice 5 does that). Composition with the generic policy is
provided by :func:`evaluate_v1_publish_decision`, which never upgrades a
review/exclude into a publish and never auto-publishes BleepingComputer unless
its *stored* credibility is already >= the policy threshold.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.pipeline.publishing.constants import (
    PendingReviewReason,
    PublishDecisionValue,
)
from app.pipeline.publishing.publishing_policy import (
    DEFAULT_V1_POLICY,
    PublishDecision,
    PublishingPolicy,
    evaluate_basic_publish_decision,
)

# Krebs is treated as at least this credibility for V1 decisions (runtime only).
_KREBS_MIN_CREDIBILITY = 4

# A BleepingComputer alert that carries a clear fraud/financial signal is treated
# as at least this credibility FOR THAT ALERT ONLY (conditional source
# eligibility). This is NOT a global promotion: the plain
# ``get_effective_source_credibility`` lookup still returns BleepingComputer's
# stored value, and the ``sources`` table is never mutated.
_BLEEPING_CONDITIONAL_CREDIBILITY = 4

# Collapsed-alphanumeric fingerprints that identify each special source. Matching
# against the collapsed form catches name variants and domains alike, e.g.
# "KrebsOnSecurity", "Krebs on Security", "https://krebsonsecurity.com" all
# collapse to a string containing "krebsonsecurity".
_KREBS_FINGERPRINT = "krebsonsecurity"
_BLEEPING_FINGERPRINT = "bleepingcomputer"


# ---------------------------------------------------------------------------
# Lexicons for BleepingComputer conditional eligibility
# ---------------------------------------------------------------------------

# Positive: clear real-world fraud / financial-crime / consumer-exposure signals.
# Conservative by construction — multi-word phrases must appear as phrases.
_FINANCIAL_FRAUD_TERMS: tuple[str, ...] = (
    "fraud",
    "scam",
    "phishing",
    "credential theft",
    "credentials",
    "account takeover",
    "ato",
    "business email compromise",
    "bec",
    "ransomware",
    "extortion",
    "crypto theft",
    "cryptocurrency theft",
    "payment fraud",
    "wire fraud",
    "identity theft",
    "data breach",
    "stolen data",
    "stolen credentials",
    "infostealer",
    "bank fraud",
    "financial fraud",
)

# Negative: purely technical / review-first signals (vuln research, patches, …).
_TECHNICAL_TERMS: tuple[str, ...] = (
    "patch",
    "patched",
    "vulnerability",
    "cve",
    "zero-day",
    "product update",
    "security update",
    "bug",
    "exploit proof-of-concept",
    "proof-of-concept",
    "poc",
    "researcher",
    "technical analysis",
)


def _compile(terms: tuple[str, ...]) -> list[re.Pattern[str]]:
    """Word-boundary patterns so acronyms (BEC/ATO/PoC/CVE) don't false-match
    inside larger words (e.g. 'bec' in 'became')."""
    return [re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE) for t in terms]


_FINANCIAL_FRAUD_PATTERNS = _compile(_FINANCIAL_FRAUD_TERMS)
_TECHNICAL_PATTERNS = _compile(_TECHNICAL_TERMS)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRuleDecision:
    """Outcome of source-specific evaluation. Pure data, no behaviour.

    ``effective_credibility`` is what the generic policy should use (Krebs is
    floored to 4; others pass through). ``is_conditionally_eligible`` is True
    only for BleepingComputer items that carry a financial/fraud signal.
    ``forces_review`` is True when the source rule must override an otherwise
    auto-publishable decision (e.g. BleepingComputer with no fraud signal).
    """

    source_name: str | None
    effective_credibility: int | None
    is_conditionally_eligible: bool
    forces_review: bool
    reason: str


# ---------------------------------------------------------------------------
# Source normalisation / identification
# ---------------------------------------------------------------------------


def normalize_source_name(source_name: str | None) -> str:
    """Collapse a source name/URL to lowercase alphanumerics only.

    ``None`` → "". "Krebs on Security" / "KrebsOnSecurity" /
    "https://krebsonsecurity.com" all → a string containing "krebsonsecurity".
    """
    if not source_name:
        return ""
    return re.sub(r"[^a-z0-9]+", "", source_name.lower())


def is_krebs_source(source_name: str | None) -> bool:
    return _KREBS_FINGERPRINT in normalize_source_name(source_name)


def is_bleepingcomputer_source(source_name: str | None) -> bool:
    return _BLEEPING_FINGERPRINT in normalize_source_name(source_name)


# ---------------------------------------------------------------------------
# Effective credibility
# ---------------------------------------------------------------------------


def get_effective_source_credibility(
    *,
    source_name: str | None,
    stored_credibility: int | None,
) -> int | None:
    """Runtime credibility used by V1 decisions (does NOT mutate the DB).

    * KrebsOnSecurity → at least 4 (``None`` stored → 4; lower → 4; higher kept).
    * BleepingComputer → stored value unchanged (no auto-promotion).
    * Other sources → stored value unchanged (``None`` stays ``None``).
    """
    if is_krebs_source(source_name):
        if stored_credibility is None:
            return _KREBS_MIN_CREDIBILITY
        return max(stored_credibility, _KREBS_MIN_CREDIBILITY)
    return stored_credibility


# ---------------------------------------------------------------------------
# BleepingComputer financial-fraud signal detection
# ---------------------------------------------------------------------------


def _build_haystack(
    *,
    title: str | None,
    summary: str | None,
    matched_keywords,
    entities_json,
    primary_category: str | None,
) -> str:
    """Flatten all text-bearing fields into one lowercase string for matching."""
    parts: list[str] = []
    for v in (title, summary, primary_category):
        if v:
            parts.append(str(v))

    if isinstance(matched_keywords, dict):
        parts.extend(str(k) for k in matched_keywords.keys())
        parts.extend(str(val) for val in matched_keywords.values() if val)
    elif isinstance(matched_keywords, (list, tuple, set)):
        parts.extend(str(x) for x in matched_keywords if x)

    if isinstance(entities_json, dict):
        names = entities_json.get("names")
        if isinstance(names, list):
            parts.extend(str(n) for n in names if n)

    return " ".join(parts).lower()


def _matches_any(haystack: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.search(haystack) for p in patterns)


def has_bleepingcomputer_financial_fraud_signal(
    *,
    title: str | None = None,
    summary: str | None = None,
    matched_keywords=None,
    entities_json: dict | None = None,
    primary_category: str | None = None,
) -> bool:
    """Conservative detector for a clear financial/fraud signal.

    Returns True iff at least one positive financial-fraud term is present in any
    of the supplied text fields. The positive lexicon is intentionally strict:
    every term denotes real-world theft / fraud / extortion / credential abuse /
    consumer-or-enterprise exposure, so its mere presence satisfies the "clearly
    indicates real-world exposure" bar even when technical terms also appear.

    Items carrying only technical signals (patch, CVE, PoC, vuln research, …) — or
    no positive signal at all — return False (route to review). This is the
    conservative default: ambiguous BleepingComputer items go to review.
    """
    haystack = _build_haystack(
        title=title,
        summary=summary,
        matched_keywords=matched_keywords,
        entities_json=entities_json,
        primary_category=primary_category,
    )
    if not haystack:
        return False
    return _matches_any(haystack, _FINANCIAL_FRAUD_PATTERNS)


# ---------------------------------------------------------------------------
# Source rule evaluation
# ---------------------------------------------------------------------------


def evaluate_source_rule(
    *,
    source_name: str | None,
    stored_credibility: int | None,
    title: str | None = None,
    summary: str | None = None,
    matched_keywords=None,
    entities_json: dict | None = None,
    primary_category: str | None = None,
) -> SourceRuleDecision:
    """Evaluate the V1 source-specific rule for one alert (pure)."""
    effective = get_effective_source_credibility(
        source_name=source_name, stored_credibility=stored_credibility
    )

    if is_krebs_source(source_name):
        # Trusted source: promoted to >=4, never forced to review for being a 3.
        return SourceRuleDecision(
            source_name=source_name,
            effective_credibility=effective,
            is_conditionally_eligible=False,
            forces_review=False,
            reason="krebs_effective_credibility_4",
        )

    if is_bleepingcomputer_source(source_name):
        has_signal = has_bleepingcomputer_financial_fraud_signal(
            title=title,
            summary=summary,
            matched_keywords=matched_keywords,
            entities_json=entities_json,
            primary_category=primary_category,
        )
        if has_signal:
            # Conditional eligibility: lift effective credibility to >= 4 for
            # THIS alert only (the stored value and the DB are untouched). A
            # higher stored value is preserved.
            conditional_credibility = max(
                stored_credibility or 0, _BLEEPING_CONDITIONAL_CREDIBILITY
            )
            return SourceRuleDecision(
                source_name=source_name,
                effective_credibility=conditional_credibility,
                is_conditionally_eligible=True,
                forces_review=False,
                reason="bleepingcomputer_conditional_fraud_signal",
            )
        return SourceRuleDecision(
            source_name=source_name,
            effective_credibility=effective,  # stored, unchanged
            is_conditionally_eligible=False,
            forces_review=True,
            reason="bleepingcomputer_review_first",
        )

    # No special source rule.
    return SourceRuleDecision(
        source_name=source_name,
        effective_credibility=effective,
        is_conditionally_eligible=False,
        forces_review=False,
        reason="no_source_rule",
    )


# ---------------------------------------------------------------------------
# Composed decision: source rule + generic policy
# ---------------------------------------------------------------------------


def evaluate_v1_publish_decision(
    *,
    signal_score_total: int | None,
    primary_category: str | None,
    source_name: str | None,
    source_credibility: int | None,
    title: str | None = None,
    summary: str | None = None,
    matched_keywords=None,
    entities_json: dict | None = None,
    policy: PublishingPolicy = DEFAULT_V1_POLICY,
) -> PublishDecision:
    """Compose source rules with the generic policy (pure, not wired in).

    Order:
      1. Evaluate the source rule → effective credibility + forces_review.
      2. Run the generic policy with the *effective* credibility.
      3. If the source rule forces review AND the alert otherwise clears every
         non-credibility gate (Critical/High band + approved category), label
         the result review/``blocked_by_source_rule`` — the source rule, not
         credibility, is the operative reason. Band/category/Medium/below-60
         gates always dominate (they are evaluated first), so a below-60,
         Medium, ``Other`` or unapproved alert keeps its generic reason.
      4. Otherwise return the generic decision unchanged. A review/exclude
         result is never upgraded to publish.

    Conditional BleepingComputer: a fraud-signal alert gets effective
    credibility 4 (via the source rule) and can auto-publish when band/category
    pass; a no-signal alert forces review. BleepingComputer's stored credibility
    in the ``sources`` table is never read up here as a publish credential and is
    never mutated — only the per-alert effective value is used.
    """
    rule = evaluate_source_rule(
        source_name=source_name,
        stored_credibility=source_credibility,
        title=title,
        summary=summary,
        matched_keywords=matched_keywords,
        entities_json=entities_json,
        primary_category=primary_category,
    )

    base = evaluate_basic_publish_decision(
        signal_score_total=signal_score_total,
        primary_category=primary_category,
        source_credibility=rule.effective_credibility,
        policy=policy,
    )

    if rule.forces_review:
        # Would this alert auto-publish if credibility weren't the issue? Force
        # credibility to a passing value and re-run the generic gates. If it then
        # auto-publishes, the only thing blocking it is the source rule.
        without_credibility_block = evaluate_basic_publish_decision(
            signal_score_total=signal_score_total,
            primary_category=primary_category,
            source_credibility=policy.min_source_credibility,
            policy=policy,
        )
        if without_credibility_block.action is PublishDecisionValue.AUTO_PUBLISH:
            return PublishDecision(
                action=PublishDecisionValue.REVIEW,
                reason=rule.reason,
                risk_band=base.risk_band,
                policy_version=base.policy_version,
                pending_review_reason=PendingReviewReason.BLOCKED_BY_SOURCE_RULE,
            )

    return base
