"""Tests for app/pipeline/signal_scorer.py — M3 Slice 3 recalibrated thresholds.

Scoring rules (M3 Slice 3):
  Financial impact:  <$1M→1, $1M–$10M→2, $10M–$100M→3, >$100M→5
  Victim scale:      single→1, multiple→2, nationwide→4
  Risk thresholds:   ≤8→low, 9–15→medium, ≥16→high
"""
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

    def test_1m_to_10m_returns_2(self):
        assert compute_financial_impact_score("$1 million") == 2
        assert compute_financial_impact_score("$4.2 million") == 2
        assert compute_financial_impact_score("$9.9 million") == 2
        assert compute_financial_impact_score("$1M") == 2
        assert compute_financial_impact_score("$5M") == 2

    def test_10m_to_100m_returns_3(self):
        assert compute_financial_impact_score("$10 million") == 3
        assert compute_financial_impact_score("$50 million") == 3
        assert compute_financial_impact_score("$99M") == 3
        assert compute_financial_impact_score("over $10 million") == 3

    def test_over_100m_returns_5(self):
        assert compute_financial_impact_score("$100 million") == 5
        assert compute_financial_impact_score("$500M") == 5
        assert compute_financial_impact_score("$1 billion") == 5
        assert compute_financial_impact_score("$2.5B") == 5

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
        # "$1M-$5M" → lower bound is $1M → score 2 (in $1M–$10M tier)
        assert compute_financial_impact_score("$1M-$5M") == 2
        # "$1M–$10M" → lower bound is $1M → score 2
        assert compute_financial_impact_score("$1M–$10M") == 2

    def test_parse_failure_defaults_to_1(self):
        assert compute_financial_impact_score("a lot of money") == 1
        assert compute_financial_impact_score("significant losses") == 1


class TestVictimScaleScore:
    def test_single_returns_1(self):
        assert compute_victim_scale_score("single") == 1
        assert compute_victim_scale_score("Single") == 1
        assert compute_victim_scale_score("SINGLE") == 1

    def test_multiple_returns_2(self):
        assert compute_victim_scale_score("multiple") == 2
        assert compute_victim_scale_score("Multiple") == 2

    def test_nationwide_returns_4(self):
        assert compute_victim_scale_score("nationwide") == 4
        assert compute_victim_scale_score("Nationwide") == 4
        assert compute_victim_scale_score("NATIONWIDE") == 4

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
    # Low boundary: ≤ 8
    def test_score_5_is_low(self):
        assert derive_risk_level(5) == "low"

    def test_score_6_is_low(self):
        assert derive_risk_level(6) == "low"

    def test_score_7_is_low(self):
        assert derive_risk_level(7) == "low"

    def test_score_8_is_low(self):
        assert derive_risk_level(8) == "low"

    # Medium boundary: 9–15
    def test_score_9_is_medium(self):
        assert derive_risk_level(9) == "medium"

    def test_score_12_is_medium(self):
        assert derive_risk_level(12) == "medium"

    def test_score_13_is_medium(self):
        assert derive_risk_level(13) == "medium"

    def test_score_15_is_medium(self):
        assert derive_risk_level(15) == "medium"

    # High boundary: ≥ 16
    def test_score_16_is_high(self):
        assert derive_risk_level(16) == "high"

    def test_score_20_is_high(self):
        assert derive_risk_level(20) == "high"

    def test_score_25_is_high(self):
        assert derive_risk_level(25) == "high"


class TestScoreCombinations:
    def test_credibility_3_all_minimum(self):
        # KrebsOnSecurity (credibility=3) + unknown impact + single victim + 1 source + stable trend
        # = 3+1+1+1+1 = 7 → low (new threshold: ≤8 is low)
        total = 3 + 1 + 1 + 1 + 1
        assert total == 7
        assert derive_risk_level(total) == "low"

    def test_credibility_5_all_maximum(self):
        # DOJ (credibility=5) + >$100M(5) + nationwide(4) + 3+ sources(5) + surge(5)
        # = 5+5+4+5+5 = 24 → high
        total = 5 + 5 + 4 + 5 + 5
        assert total == 24
        assert derive_risk_level(total) == "high"

    def test_typical_gov_source_now_medium(self):
        # Typical SEC press release: credibility=5 + $5M(2) + multiple(2) + 1src(1) + stable(1)
        # = 5+2+2+1+1 = 11 → medium (was HIGH under M2 thresholds: 5+3+3+1+1=13→high)
        total = 5 + 2 + 2 + 1 + 1
        assert total == 11
        assert derive_risk_level(total) == "medium"

    def test_gov_source_new_keyword_still_medium(self):
        # SEC + $5M + multiple + 1src + new keyword (trend=3)
        # = 5+2+2+1+3 = 13 → medium (was HIGH under M2)
        total = 5 + 2 + 2 + 1 + 3
        assert total == 13
        assert derive_risk_level(total) == "medium"

    def test_exceptional_still_high(self):
        # DOJ (5) + $200M(5) + nationwide(4) + 1src(1) + stable(1) = 16 → high
        total = 5 + 5 + 4 + 1 + 1
        assert total == 16
        assert derive_risk_level(total) == "high"

    def test_tier1_boundary_exactly_16(self):
        # Minimum score that qualifies as HIGH and Tier 1 auto-publish
        assert derive_risk_level(16) == "high"

    def test_large_fraud_multiple_sources_high(self):
        # SEC (5) + $50M(3) + nationwide(4) + 2src(3) + surge(5) = 20 → high
        total = 5 + 3 + 4 + 3 + 5
        assert total == 20
        assert derive_risk_level(total) == "high"

    def test_krebs_typical_medium(self):
        # KrebsOnSecurity (3) + $5M(2) + multiple(2) + 1src(1) + stable(1) = 9 → medium
        total = 3 + 2 + 2 + 1 + 1
        assert total == 9
        assert derive_risk_level(total) == "medium"

    def test_krebs_minimal_low(self):
        # KrebsOnSecurity (3) + unknown(1) + single(1) + 1src(1) + stable(1) = 7 → low
        total = 3 + 1 + 1 + 1 + 1
        assert total == 7
        assert derive_risk_level(total) == "low"
