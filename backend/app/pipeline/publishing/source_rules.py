"""V1 source-specific publishing rules (Slice 3 / 3.1 — pure, deterministic, no DB).

Adds the source-aware layer on top of the Slice 2 generic policy:

  * KrebsOnSecurity is effectively trusted for V1 decisions — treated as
    **effective credibility 4** (a runtime decision only — the ``sources`` table
    is NOT mutated).
  * BleepingComputer is **not globally promoted**. It remains review-first by
    default, but a BleepingComputer alert with a *clear* fraud / financial-victim
    signal is *conditionally source-eligible* and receives **effective
    credibility 4 for that alert only** — never a stored credibility change.
    ``get_effective_source_credibility`` still returns BleepingComputer's stored
    value; the per-alert lift lives only inside :func:`evaluate_source_rule`. The
    signal is tiered (M2 precision tuning): a direct fraud term (phishing, BEC,
    payment/bank/wire fraud, account takeover, crypto/wallet theft, identity
    theft, consumer scam, infostealer, …) qualifies on its own; ransomware /
    extortion and breach / data-exposure qualify only with impact / victim
    context; and primarily-technical items (CVE / patch / PoC / advisory /
    analysis) stay review-first. Entity names are not part of the signal.
  * All other sources have no special rule (effective credibility = stored).

Everything here is pure and side-effect free. Composition with the generic
policy is provided by :func:`evaluate_v1_publish_decision`, which never upgrades
a review/exclude into a publish (it is wired into the live pipeline via
``alert_pipeline``). A qualifying (fraud-signal) BleepingComputer alert can
auto-publish via its per-alert conditional credibility when the band and
category gates also pass; a non-qualifying one is routed to review. The
``sources`` table is never read as a publish credential here and is never
mutated — only the per-alert effective credibility is used.
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
# Lexicons for the BleepingComputer conditional fraud signal (M2 precision tuning)
# ---------------------------------------------------------------------------
#
# The signal is intentionally tiered rather than a single OR-match over a wide
# haystack:
#   (1) DIRECT fraud terms are sufficient on their own (clear fraud / financial-
#       victim intent), even when technical terms also appear.
#   (2) RANSOMWARE / extortion qualifies ONLY together with an IMPACT term (3) —
#       a bare "ransomware" mention in a vuln/patch article is NOT enough.
#   (4) BREACH / data-exposure qualifies ONLY together with a victim/financial
#       relevance term (5) — generic "data breach" alone is NOT enough.
#   (6) TECHNICAL context vetoes a (2)/(4) contextual signal (but never a (1)
#       direct signal), so primarily-technical items stay review-first.
# Entity names are deliberately NOT searched (see ``has_bleepingcomputer_...``).

# (1) DIRECT fraud / financial-victim signals — sufficient on their own.
_DIRECT_FRAUD_TERMS: tuple[str, ...] = (
    "phishing", "spear phishing", "spear-phishing", "smishing", "vishing",
    "credential theft", "credential harvesting", "stolen credentials",
    "harvested credentials", "account takeover", "ato",
    "business email compromise", "bec",
    "payment fraud", "bank fraud", "wire fraud", "invoice fraud",
    "card fraud", "credit card theft", "carding",
    "crypto theft", "cryptocurrency theft", "wallet theft", "wallet drainer",
    "seed phrase", "investment scam", "investment fraud", "romance scam",
    "consumer scam", "tech support scam", "gift card scam", "refund scam",
    "identity theft", "fraud campaign", "scam campaign",
    "financial fraud", "infostealer", "money laundering",
)

# (2) RANSOMWARE / extortion family — needs an IMPACT term (3) to qualify.
_RANSOMWARE_TERMS: tuple[str, ...] = (
    "ransomware", "extortion", "double extortion",
)

# (3) IMPACT context — financial / victim / operational consequence.
_IMPACT_TERMS: tuple[str, ...] = (
    "payment", "payments", "paid", "ransom", "extortion",
    "victim", "victims", "customers", "consumers", "clients",
    "businesses", "enterprises", "hospital", "hospitals", "patients",
    "financial loss", "financial losses", "stolen funds", "funds stolen",
    "money stolen", "data theft", "data stolen", "data leak", "data leaked",
    "leaked data", "exfiltration", "exfiltrated",
    "operations disrupted", "disrupted operations",
    "disrupt", "disrupts", "disrupting", "disrupted", "shut down",
    "million", "millions", "billion",
)

# (4) BREACH / data-exposure family — needs a victim/financial term (5).
_BREACH_TERMS: tuple[str, ...] = (
    "data breach", "breach", "data exposure", "data exposed", "exposes",
    "exposed", "leaked", "leak", "database exposed", "misconfigured database",
)

# (5) BREACH victim / financial relevance.
_BREACH_IMPACT_TERMS: tuple[str, ...] = (
    "customers", "consumers", "clients", "users",
    "personal information", "personal data", "personally identifiable", "pii",
    "bank account", "bank accounts", "credit card", "credit cards",
    "payment data", "payment card", "payment information",
    "identity theft", "stolen credentials", "fraud risk",
    "financial data", "financial information",
    "ssn", "social security number", "social security numbers",
    "passwords", "medical records", "health records",
)

# (6) TECHNICAL context — vetoes a contextual (ransomware/breach) signal, never a
#     direct fraud signal. Primarily-technical BleepingComputer items stay review-first.
_TECHNICAL_TERMS: tuple[str, ...] = (
    "cve", "patch", "patched", "patch tuesday", "security update",
    "product update", "software update", "vulnerability", "vulnerabilities",
    "zero-day", "0-day", "proof-of-concept", "proof of concept", "poc",
    "exploit poc", "security advisory", "advisory", "bug fix", "bugfix",
    "remote code execution", "rce", "privilege escalation",
    "denial of service", "ddos", "technical analysis", "malware analysis",
    "researcher", "researchers", "reverse engineering",
)


def _compile(terms: tuple[str, ...]) -> list[re.Pattern[str]]:
    """Word-boundary patterns so acronyms (BEC/ATO/PoC/CVE) don't false-match
    inside larger words (e.g. 'bec' in 'became', 'ato' in 'potato')."""
    return [re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE) for t in terms]


_DIRECT_FRAUD_PATTERNS = _compile(_DIRECT_FRAUD_TERMS)
_RANSOMWARE_PATTERNS = _compile(_RANSOMWARE_TERMS)
_IMPACT_PATTERNS = _compile(_IMPACT_TERMS)
_BREACH_PATTERNS = _compile(_BREACH_TERMS)
_BREACH_IMPACT_PATTERNS = _compile(_BREACH_IMPACT_TERMS)
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
    primary_category: str | None,
) -> str:
    """Flatten the text-bearing fields into one lowercase string for matching.

    Entity names are intentionally NOT included: a fraud word appearing inside a
    company/product name (e.g. "Identity Theft Protection Inc.") must not, by
    itself, trip the fraud signal. Only article text — title, summary, category,
    and matched keywords — is searched.
    """
    parts: list[str] = []
    for v in (title, summary, primary_category):
        if v:
            parts.append(str(v))

    if isinstance(matched_keywords, dict):
        parts.extend(str(k) for k in matched_keywords.keys())
        parts.extend(str(val) for val in matched_keywords.values() if val)
    elif isinstance(matched_keywords, (list, tuple, set)):
        parts.extend(str(x) for x in matched_keywords if x)

    return " ".join(parts).lower()


def _matches_any(haystack: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.search(haystack) for p in patterns)


def _has_direct_fraud_signal(text: str) -> bool:
    """Strong, unambiguous fraud / financial-victim term — sufficient alone."""
    return _matches_any(text, _DIRECT_FRAUD_PATTERNS)


def _has_ransomware_with_impact(text: str) -> bool:
    """Ransomware/extortion AND a financial/victim/operational impact term."""
    return _matches_any(text, _RANSOMWARE_PATTERNS) and _matches_any(text, _IMPACT_PATTERNS)


def _has_breach_with_victim_or_financial_impact(text: str) -> bool:
    """Breach/data-exposure AND a consumer/financial/victim relevance term."""
    return _matches_any(text, _BREACH_PATTERNS) and _matches_any(text, _BREACH_IMPACT_PATTERNS)


def _has_technical_context(text: str) -> bool:
    """Primarily-technical framing (CVE/patch/PoC/advisory/analysis/…)."""
    return _matches_any(text, _TECHNICAL_PATTERNS)


def has_bleepingcomputer_financial_fraud_signal(
    *,
    title: str | None = None,
    summary: str | None = None,
    matched_keywords=None,
    entities_json: dict | None = None,
    primary_category: str | None = None,
) -> bool:
    """Tiered detector for a *clear* fraud / financial-victim signal (M2 tuned).

    Decision (conservative — prefer review when uncertain):

      * A **direct** fraud term (phishing, BEC, payment/bank/wire fraud, account
        takeover, crypto/wallet theft, identity theft, consumer scam, infostealer,
        …) is sufficient on its own — even alongside technical terms, because a
        real phishing campaign may cite a CVE and is still fraud-relevant.
      * **Ransomware / extortion** qualifies only with an impact term (payment,
        ransom, victims, customers, financial loss, operations disrupted, …); a
        bare "ransomware" mention in a vuln/patch article does NOT qualify.
      * **Breach / data-exposure** qualifies only with a consumer/financial/victim
        term (customers, payment data, identity theft, SSN, …); generic "data
        breach" alone does NOT qualify.
      * A ransomware/breach contextual signal is **vetoed** when the item carries
        technical framing (CVE/patch/PoC/advisory/analysis), so primarily-technical
        BleepingComputer items stay review-first. The veto never blocks a direct
        fraud signal.

    ``entities_json`` is accepted for call-site compatibility but intentionally
    NOT searched — entity names alone cannot trip the signal.
    """
    text = _build_haystack(
        title=title,
        summary=summary,
        matched_keywords=matched_keywords,
        primary_category=primary_category,
    )
    if not text:
        return False

    if _has_direct_fraud_signal(text):
        return True

    contextual = (
        _has_ransomware_with_impact(text)
        or _has_breach_with_victim_or_financial_impact(text)
    )
    if contextual and not _has_technical_context(text):
        return True

    return False


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
