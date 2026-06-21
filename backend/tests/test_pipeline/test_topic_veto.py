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
