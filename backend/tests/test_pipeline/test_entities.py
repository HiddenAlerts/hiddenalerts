"""V1 Slice 4 — shared entity-utility tests (pure, deterministic)."""
import pytest

from app.pipeline.entities import (
    filter_non_agency_entities,
    is_agency_name,
    normalize_entity_name,
)


@pytest.mark.parametrize(
    "name",
    [
        "FBI",
        "Federal Bureau of Investigation",
        "Department of Justice",
        "DOJ",
        "SEC",
        "Securities and Exchange Commission",
        "FTC",
        "FinCEN",
        "IC3",
        "Internet Crime Complaint Center",
        "U.S. Attorney",
        "United States Attorney",
        "law enforcement",
        "federal authorities",
    ],
)
def test_agency_names_detected(name):
    assert is_agency_name(name) is True


@pytest.mark.parametrize(
    "name",
    ["Coinbase", "John Smith", "ACME Corporation", "Binance", "Evil Corp", "Wells Fargo"],
)
def test_real_subjects_not_agencies(name):
    assert is_agency_name(name) is False


def test_agency_word_boundaries_no_false_positive():
    # 'securities' contains 'sec' but must not match the standalone 'sec' agency.
    assert is_agency_name("Securities Trading Firm LLC") is False
    # 'operation' is an agency-program token; a company literally named with it
    # would match — but ordinary names like below do not contain it.
    assert is_agency_name("Decentralized Finance Inc") is False


def test_none_and_blank_not_agency():
    assert is_agency_name(None) is False
    assert is_agency_name("") is False
    assert is_agency_name("   ") is False


def test_filter_non_agency_entities():
    assert filter_non_agency_entities(["FBI", "Coinbase"]) == ["Coinbase"]
    assert filter_non_agency_entities(["FBI", "DOJ"]) == []
    assert filter_non_agency_entities(["Coinbase", "Binance"]) == ["Coinbase", "Binance"]
    assert filter_non_agency_entities(None) == []
    assert filter_non_agency_entities([]) == []
    # Blank/whitespace entries dropped; order + original spelling preserved.
    assert filter_non_agency_entities(["", "  ", "Acme Corp"]) == ["Acme Corp"]


def test_normalize_entity_name():
    assert normalize_entity_name(None) == ""
    assert normalize_entity_name("  Coinbase ") == "coinbase"
    assert normalize_entity_name("ACME Corp") == "acme corp"
