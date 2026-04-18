"""Tests for app/pipeline/signal_scorer.py — pure arithmetic, no DB needed for most tests."""
import pytest

from app.pipeline.signal_scorer import (
    compute_cross_source_score,
    compute_financial_impact_score,
    compute_victim_scale_score,
    derive_risk_level,
)


class TestFinancialImpactScore:
    def test_under_1m_returns_1(self):
        assert compute_financial_impact_score("$500,000") == 1
        assert compute_financial_impact_score("$900K") == 1
        assert compute_financial_impact_score("$250 thousand") == 1

    def test_1m_to_10m_returns_3(self):
        assert compute_financial_impact_score("$1 million") == 3
        assert compute_financial_impact_score("$4.2 million") == 3
        assert compute_financial_impact_score("$9.9 million") == 3
        assert compute_financial_impact_score("$1M") == 3
        assert compute_financial_impact_score("$5M") == 3

    def test_over_10m_returns_5(self):
        assert compute_financial_impact_score("$10 million") == 5
        assert compute_financial_impact_score("$50 million") == 5
        assert compute_financial_impact_score("$100M") == 5
        assert compute_financial_impact_score("over $10 million") == 5

    def test_billions_returns_5(self):
        assert compute_financial_impact_score("$1 billion") == 5
        assert compute_financial_impact_score("$2.5B") == 5

    def test_unknown_returns_1(self):
        assert compute_financial_impact_score("unknown") == 1
        assert compute_financial_impact_score("Unknown") == 1
        assert compute_financial_impact_score("UNKNOWN") == 1

    def test_none_returns_1(self):
        assert compute_financial_impact_score("none") == 1
        assert compute_financial_impact_score("None") == 1

    def test_empty_string_returns_1(self):
        assert compute_financial_impact_score("") == 1

    def test_n_a_returns_1(self):
        assert compute_financial_impact_score("n/a") == 1
        assert compute_financial_impact_score("not stated") == 1

    def test_range_uses_lower_bound(self):
        # "$1M-$5M" → lower bound is $1M → score 3
        assert compute_financial_impact_score("$1M-$5M") == 3
        # "$1M–$10M" → lower bound is $1M → score 3
        assert compute_financial_impact_score("$1M–$10M") == 3

    def test_parse_failure_defaults_to_1(self):
        assert compute_financial_impact_score("a lot of money") == 1
        assert compute_financial_impact_score("significant losses") == 1


class TestVictimScaleScore:
    def test_single_returns_1(self):
        assert compute_victim_scale_score("single") == 1
        assert compute_victim_scale_score("Single") == 1
        assert compute_victim_scale_score("SINGLE") == 1

    def test_multiple_returns_3(self):
        assert compute_victim_scale_score("multiple") == 3
        assert compute_victim_scale_score("Multiple") == 3

    def test_nationwide_returns_5(self):
        assert compute_victim_scale_score("nationwide") == 5
        assert compute_victim_scale_score("Nationwide") == 5
        assert compute_victim_scale_score("NATIONWIDE") == 5

    def test_unknown_string_returns_1(self):
        assert compute_victim_scale_score("global") == 1
        assert compute_victim_scale_score("regional") == 1
        assert compute_victim_scale_score("") == 1

    def test_none_like_empty_returns_1(self):
        assert compute_victim_scale_score("") == 1


class TestCrossSourceScore:
    def test_zero_returns_1(self):
        assert compute_cross_source_score(0) == 1

    def test_one_returns_1(self):
        assert compute_cross_source_score(1) == 1

    def test_two_returns_3(self):
        assert compute_cross_source_score(2) == 3

    def test_three_returns_5(self):
        assert compute_cross_source_score(3) == 5

    def test_many_returns_5(self):
        assert compute_cross_source_score(10) == 5


class TestDeriveRiskLevel:
    def test_score_5_is_low(self):
        assert derive_risk_level(5) == "low"

    def test_score_6_is_low(self):
        assert derive_risk_level(6) == "low"

    def test_score_7_is_medium(self):
        assert derive_risk_level(7) == "medium"

    def test_score_12_is_medium(self):
        assert derive_risk_level(12) == "medium"

    def test_score_13_is_high(self):
        assert derive_risk_level(13) == "high"

    def test_score_25_is_high(self):
        assert derive_risk_level(25) == "high"

    def test_score_20_is_high(self):
        assert derive_risk_level(20) == "high"


class TestScoreCombinations:
    def test_credibility_3_all_minimum(self):
        # KrebsOnSecurity (credibility=3) + unknown impact + single victim + 1 source + stable trend
        # = 3+1+1+1+1 = 7 → medium
        total = 3 + 1 + 1 + 1 + 1
        assert total == 7
        assert derive_risk_level(total) == "medium"

    def test_credibility_5_all_maximum(self):
        # DOJ (credibility=5) + >$10M + nationwide + 3+ sources + surge
        # = 5+5+5+5+5 = 25 → high
        total = 5 + 5 + 5 + 5 + 5
        assert total == 25
        assert derive_risk_level(total) == "high"

    def test_credibility_5_medium_all_factors_mid(self):
        # FBI (5) + $5M (3) + multiple (3) + 1 source (1) + stable (1) = 13 → high
        total = 5 + 3 + 3 + 1 + 1
        assert total == 13
        assert derive_risk_level(total) == "high"
