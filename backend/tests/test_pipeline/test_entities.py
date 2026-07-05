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
        "Federal Trade Commission",
        "FinCEN",
        "Financial Crimes Enforcement Network",
        "IC3",
        "Internet Crime Complaint Center",
        "U.S. Attorney",
        "US Attorney",
        "United States Attorney",
        "law enforcement",
        "government",
        "federal authorities",
    ],
)
def test_agency_names_detected(name):
    assert is_agency_name(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "Coinbase",
        "John Smith",
        "KrebsOnSecurity",
        "BleepingComputer",
        "ACME Corporation",
        "Binance",
        "Wells Fargo",
    ],
)
def test_real_subjects_not_agencies(name):
    assert is_agency_name(name) is False


def test_agency_word_boundaries_no_false_positive():
    # 'securities' contains 'sec' but must not match the standalone 'sec' agency.
    assert is_agency_name("Securities Trading Firm LLC") is False


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


# --- Slice 5: broad generic-term precision -----------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "government",
        "Government",
        "law enforcement",
        "federal authorities",
        "Operation Winter SHIELD",  # named LE operation, no corporate suffix
        "Operation Crypto Shield",
    ],
)
def test_broad_generic_terms_still_detected(name):
    assert is_agency_name(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "Government Employees Insurance Company",  # GEICO — real org
        "Operation Finance LLC",                   # real org with corp suffix
        "Government Technology Solutions Inc",
        "Operation Smart Holdings",
    ],
)
def test_broad_generic_terms_not_filtered_in_real_org_names(name):
    assert is_agency_name(name) is False
