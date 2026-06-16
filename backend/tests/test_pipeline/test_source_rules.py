"""V1 Slice 3 — source-rule pure helper tests (deterministic, no DB)."""
import pytest

from app.pipeline.publishing.constants import (
    PendingReviewReason,
    PublishDecisionValue,
    RiskBandValue,
)
from app.pipeline.publishing.source_rules import (
    SourceRuleDecision,
    evaluate_source_rule,
    evaluate_v1_publish_decision,
    get_effective_source_credibility,
    has_bleepingcomputer_financial_fraud_signal,
    is_bleepingcomputer_source,
    is_krebs_source,
    normalize_source_name,
)

_CRITICAL = 22  # -> 88/100
_MEDIUM = 16    # -> 64/100
_BELOW = 10     # -> 40/100
_APPROVED = "Cybercrime"


# --- Source normalization / identification -----------------------------------


@pytest.mark.parametrize(
    "name",
    ["KrebsOnSecurity", "Krebs on Security", "krebs on security", "https://krebsonsecurity.com"],
)
def test_krebs_variants_detected(name):
    assert is_krebs_source(name) is True
    assert is_bleepingcomputer_source(name) is False


@pytest.mark.parametrize(
    "name",
    ["BleepingComputer", "Bleeping Computer", "bleeping computer", "https://www.bleepingcomputer.com"],
)
def test_bleeping_variants_detected(name):
    assert is_bleepingcomputer_source(name) is True
    assert is_krebs_source(name) is False


@pytest.mark.parametrize("name", ["SEC Press Releases", "IC3 Press Releases", "", None, "Krebs Industries LLC unrelated"])
def test_unknown_sources_not_special(name):
    if name == "Krebs Industries LLC unrelated":
        # 'krebsindustries...' does not contain the 'krebsonsecurity' fingerprint.
        assert is_krebs_source(name) is False
    else:
        assert is_krebs_source(name) is False
    assert is_bleepingcomputer_source(name) is False


def test_normalize_source_name():
    assert normalize_source_name(None) == ""
    assert normalize_source_name("Krebs on Security") == "krebsonsecurity"
    assert "bleepingcomputer" in normalize_source_name("https://www.bleepingcomputer.com")


# --- Effective credibility ---------------------------------------------------


@pytest.mark.parametrize(
    "name,stored,expected",
    [
        ("KrebsOnSecurity", 3, 4),
        ("KrebsOnSecurity", 4, 4),
        ("KrebsOnSecurity", 5, 5),
        ("KrebsOnSecurity", None, 4),       # trusted source: missing → 4
        ("BleepingComputer", 3, 3),         # no auto-promotion
        ("BleepingComputer", 4, 4),
        ("SEC Press Releases", 4, 4),
        ("SEC Press Releases", None, None),  # generic missing stays None
    ],
)
def test_effective_credibility(name, stored, expected):
    assert (
        get_effective_source_credibility(source_name=name, stored_credibility=stored)
        == expected
    )


# --- BleepingComputer positive signals ---------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Massive phishing campaign targets bank customers",
        "Account takeover attacks surge against retailers",
        "Hackers perform credential theft via fake login pages",
        "Ransomware gang demands extortion payment after data breach",
        "Cryptocurrency theft drains millions from DeFi wallets",
        "Payment fraud scheme hits e-commerce platforms",
        "Massive data breach exposes stolen credentials of millions",
        "New BEC scam tricks finance teams into wire fraud",
        "Infostealer malware harvests banking credentials",
    ],
)
def test_bleeping_positive_signals_true(title):
    assert (
        has_bleepingcomputer_financial_fraud_signal(title=title, primary_category="Cybercrime")
        is True
    )


# --- BleepingComputer review-first (technical-only) signals ------------------


@pytest.mark.parametrize(
    "title",
    [
        "Microsoft releases patch for Windows kernel issue",
        "New CVE vulnerability disclosed in OpenSSL",
        "Google ships product update for Chrome browser",
        "Researcher publishes proof-of-concept exploit (PoC)",
        "Technical analysis of a memory-safety bug by a researcher",
        "Security update addresses zero-day in router firmware",
    ],
)
def test_bleeping_technical_only_signals_false(title):
    assert (
        has_bleepingcomputer_financial_fraud_signal(title=title, primary_category="Cybercrime")
        is False
    )


def test_acronym_word_boundaries_no_false_positive():
    # 'became' must not match 'bec'; 'potato' must not match 'ato'.
    assert (
        has_bleepingcomputer_financial_fraud_signal(
            title="The company became a potato supplier", primary_category="Other"
        )
        is False
    )


def test_signal_detected_in_matched_keywords_and_entities():
    assert (
        has_bleepingcomputer_financial_fraud_signal(matched_keywords=["phishing", "credential"])
        is True
    )
    assert (
        has_bleepingcomputer_financial_fraud_signal(
            matched_keywords={"phishing": 1}
        )
        is True
    )
    assert has_bleepingcomputer_financial_fraud_signal(title=None, summary=None) is False


# --- evaluate_source_rule ----------------------------------------------------


def test_source_rule_krebs_promoted_not_forced_review():
    d = evaluate_source_rule(source_name="KrebsOnSecurity", stored_credibility=3)
    assert isinstance(d, SourceRuleDecision)
    assert d.effective_credibility == 4
    assert d.forces_review is False
    assert d.is_conditionally_eligible is False


def test_source_rule_bleeping_with_signal_conditionally_eligible():
    # Slice 3.1: a fraud-signal BleepingComputer alert gets per-alert effective
    # credibility 4 (conditional eligibility) — stored value is NOT mutated.
    d = evaluate_source_rule(
        source_name="BleepingComputer",
        stored_credibility=3,
        title="Phishing campaign steals banking credentials",
    )
    assert d.effective_credibility == 4
    assert d.is_conditionally_eligible is True
    assert d.forces_review is False
    assert d.reason == "bleepingcomputer_conditional_fraud_signal"


def test_source_rule_bleeping_signal_preserves_higher_stored_credibility():
    d = evaluate_source_rule(
        source_name="BleepingComputer",
        stored_credibility=5,
        title="Ransomware extortion drains bank accounts",
    )
    assert d.effective_credibility == 5  # max(stored, 4) keeps the higher value


def test_get_effective_credibility_does_not_globally_promote_bleeping():
    # The plain lookup never promotes BleepingComputer — promotion is conditional
    # and lives only inside evaluate_source_rule for qualifying alerts.
    assert (
        get_effective_source_credibility(
            source_name="BleepingComputer", stored_credibility=3
        )
        == 3
    )


def test_source_rule_bleeping_no_signal_forces_review():
    d = evaluate_source_rule(
        source_name="BleepingComputer",
        stored_credibility=4,
        title="Microsoft releases patch for Windows",
    )
    assert d.effective_credibility == 4
    assert d.is_conditionally_eligible is False
    assert d.forces_review is True
    assert d.reason == "bleepingcomputer_review_first"


def test_source_rule_other_source_no_rule():
    d = evaluate_source_rule(source_name="SEC Press Releases", stored_credibility=4)
    assert d.effective_credibility == 4
    assert d.forces_review is False
    assert d.is_conditionally_eligible is False
    assert d.reason == "no_source_rule"


# --- Composed decision -------------------------------------------------------


def _v1(score, category, name, cred, **text):
    return evaluate_v1_publish_decision(
        signal_score_total=score,
        primary_category=category,
        source_name=name,
        source_credibility=cred,
        **text,
    )


def test_krebs_critical_stored3_auto_publishes_via_effective_4():
    d = _v1(_CRITICAL, _APPROVED, "KrebsOnSecurity", 3)
    assert d.action is PublishDecisionValue.AUTO_PUBLISH
    assert d.risk_band is RiskBandValue.CRITICAL


def test_bleeping_critical_stored3_phishing_auto_publishes_conditionally():
    # Slice 3.1 change: conditional eligibility lets a fraud-signal Critical
    # BleepingComputer alert auto-publish even with stored credibility 3.
    d = _v1(_CRITICAL, _APPROVED, "BleepingComputer", 3, title="Phishing scam steals credentials")
    assert d.action is PublishDecisionValue.AUTO_PUBLISH
    assert d.risk_band is RiskBandValue.CRITICAL


def test_bleeping_critical_stored3_patch_only_review_source_rule():
    d = _v1(_CRITICAL, _APPROVED, "BleepingComputer", 3, title="Microsoft releases security patch")
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.BLOCKED_BY_SOURCE_RULE
    assert d.reason == "bleepingcomputer_review_first"


def test_bleeping_medium_stored3_fraud_review_score():
    d = _v1(_MEDIUM, _APPROVED, "BleepingComputer", 3, title="Phishing fraud campaign")
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.BLOCKED_BY_SCORE


def test_bleeping_below60_stored3_fraud_excluded():
    d = _v1(_BELOW, _APPROVED, "BleepingComputer", 3, title="Phishing fraud campaign")
    assert d.action is PublishDecisionValue.EXCLUDE
    assert d.pending_review_reason is PendingReviewReason.EXCLUDED_LOW_SCORE


def test_bleeping_critical_stored3_other_category_fraud_manual_review():
    d = _v1(_CRITICAL, "Other", "BleepingComputer", 3, title="Phishing fraud campaign")
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.MANUAL_REVIEW_ONLY


def test_bleeping_critical_stored3_unknown_category_fraud_blocked_by_category():
    d = _v1(_CRITICAL, "Weather", "BleepingComputer", 3, title="Phishing fraud campaign")
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.BLOCKED_BY_CATEGORY


def test_bleeping_critical_stored4_phishing_auto_publishes():
    d = _v1(_CRITICAL, _APPROVED, "BleepingComputer", 4, title="Phishing scam steals credentials")
    assert d.action is PublishDecisionValue.AUTO_PUBLISH


def test_bleeping_critical_stored4_patch_only_review_source_rule():
    d = _v1(_CRITICAL, _APPROVED, "BleepingComputer", 4, title="Microsoft releases security patch")
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.BLOCKED_BY_SOURCE_RULE
    assert d.reason == "bleepingcomputer_review_first"


def test_bleeping_medium_fraud_stored4_review_score():
    d = _v1(_MEDIUM, _APPROVED, "BleepingComputer", 4, title="Phishing fraud campaign")
    assert d.action is PublishDecisionValue.REVIEW
    assert d.pending_review_reason is PendingReviewReason.BLOCKED_BY_SCORE


def test_bleeping_below60_fraud_stored4_excluded():
    d = _v1(_BELOW, _APPROVED, "BleepingComputer", 4, title="Phishing fraud campaign")
    assert d.action is PublishDecisionValue.EXCLUDE
    assert d.pending_review_reason is PendingReviewReason.EXCLUDED_LOW_SCORE


def test_other_source_critical_approved_cred4_auto_publishes():
    d = _v1(_CRITICAL, _APPROVED, "SEC Press Releases", 4)
    assert d.action is PublishDecisionValue.AUTO_PUBLISH


def test_composed_never_upgrades_review_to_publish():
    # Other source, Medium → review must remain review regardless of source rule.
    d = _v1(_MEDIUM, _APPROVED, "SEC Press Releases", 5)
    assert d.action is PublishDecisionValue.REVIEW
