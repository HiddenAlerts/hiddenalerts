"""OPEN-5 — deterministic out-of-scope topic-exclusion veto (pure, no DB)."""
import pytest

from app.pipeline.publishing.topic_veto import should_route_to_review_by_topic as veto


@pytest.mark.parametrize(
    "title",
    [
        "Terrorist bombing kills civilians in the capital",
        "Nation-state espionage breaches a defense network",
        "Drug trafficking ring busted at the border",
        "Fugitive captured after a nationwide manhunt",
        "Gang members charged in a homicide case",
        "Weapons trafficking operation dismantled",
        "ISIS cell planned an attack",
    ],
)
def test_out_of_scope_routes_to_review(title):
    # No fraud signal → out-of-scope term routes to review.
    assert veto(title=title, primary_category="Cybercrime") is True


@pytest.mark.parametrize(
    "title",
    [
        "Terrorism financing via a money laundering ring",   # money laundering
        "Drug trafficking ring used a shell company",        # shell company
        "Gang ran a wire fraud and phishing scheme",         # wire fraud / phishing
    ],
)
def test_out_of_scope_with_fraud_signal_is_not_vetoed(title):
    # A clear fraud / financial-crime anti-veto term overrides the topic veto.
    assert veto(title=title, primary_category="Money Laundering") is False


@pytest.mark.parametrize(
    "title",
    [
        "Phishing campaign steals bank credentials",
        "Investment fraud Ponzi scheme collapses",
        "Account takeover hits online banking customers",
    ],
)
def test_clean_fraud_is_not_vetoed(title):
    assert veto(title=title, primary_category="Cybercrime") is False


def test_empty_text_not_vetoed():
    assert veto(title=None, summary=None, primary_category=None) is False


def test_word_boundary_no_false_match():
    # 'gangway' must not trip 'gang'; ordinary text isn't vetoed.
    assert veto(title="Crew repairs the gangway on the ferry", primary_category="Other") is False


def test_signal_detected_in_summary_and_matched_keywords():
    assert veto(summary="An ISIS-linked weapons cell", primary_category="Other") is True
    assert veto(title="Routine update", matched_keywords=["espionage"], primary_category="Cybercrime") is True


# --- anti-veto must NOT be suppressed by a stale/mis-tagged matched_keyword ----


def test_csam_not_suppressed_by_mistagged_fraud_keyword():
    # The id-89 regression: a CSAM story whose matched_keywords were mis-tagged
    # "crypto theft"/"ransomware" (article mentions neither) must still be vetoed.
    assert veto(
        title="UK probes Telegram, teen chat sites over CSAM sharing concerns",
        summary="Ofcom is investigating the sharing of child sexual abuse material.",
        matched_keywords=["ransomware", "crypto theft"],
        primary_category="Cybercrime",
    ) is True


def test_absolute_csam_overrides_even_real_text_fraud_term():
    # Child-exploitation is absolute: even a genuine fraud term in the text does
    # not let it through (routes to review, never auto-publish).
    assert veto(
        title="CSAM ring busted",
        summary="The ring laundered money via crypto wallets.",
        primary_category="Cybercrime",
    ) is True


def test_anti_veto_only_in_keywords_does_not_suppress():
    # Non-absolute out-of-scope: an anti-veto term present ONLY in matched_keywords
    # (not the article text) must NOT cancel the veto.
    assert veto(
        title="Drug trafficking ring arrested at the border",
        matched_keywords=["wire fraud", "money laundering"],
        primary_category="Other",
    ) is True


def test_anti_veto_in_article_text_still_suppresses():
    # Anti-veto term in the actual title/summary still overrides (unchanged behavior).
    assert veto(
        title="Terrorism financing ring laundered money via a shell company",
        primary_category="Money Laundering",
    ) is False


# --- lexicon precision: bare "gang" must not over-fire on in-scope cyber actors -


def test_bare_gang_does_not_overfire_on_cyber_actor():
    # "ShinyHunters gang" / "cybercrime gang" are fraud actors, not street gangs.
    assert veto(title="ShinyHunters gang breached retailer systems", primary_category="Cybercrime") is False
    assert veto(title="Cybercrime gang stole customer records", primary_category="Cybercrime") is False


def test_genuine_street_gang_still_vetoed():
    assert veto(title="Street gang shooting leaves three dead", primary_category="Other") is True
    assert veto(title="Gang member convicted in a fatal shooting", primary_category="Other") is True
