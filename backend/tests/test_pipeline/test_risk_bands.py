"""V1 Slice 2 — risk-band mapping tests (pure, deterministic)."""
import pytest

from app.pipeline.publishing.constants import RiskBandValue
from app.pipeline.publishing.risk_bands import compute_risk_band, compute_score_100


@pytest.mark.parametrize(
    "internal,expected",
    [
        (None, RiskBandValue.BELOW_60),
        (5, RiskBandValue.BELOW_60),
        (14, RiskBandValue.BELOW_60),
        (15, RiskBandValue.MEDIUM),
        (16, RiskBandValue.MEDIUM),
        (17, RiskBandValue.MEDIUM),
        (18, RiskBandValue.HIGH),
        (19, RiskBandValue.HIGH),
        (20, RiskBandValue.CRITICAL),
        (21, RiskBandValue.CRITICAL),
        (25, RiskBandValue.CRITICAL),
    ],
)
def test_compute_risk_band_boundaries(internal, expected):
    assert compute_risk_band(internal) is expected


@pytest.mark.parametrize(
    "invalid,expected",
    [
        (0, RiskBandValue.BELOW_60),
        (-5, RiskBandValue.BELOW_60),
        (4, RiskBandValue.BELOW_60),
        (26, RiskBandValue.CRITICAL),   # out-of-range high still safely critical
        (999, RiskBandValue.CRITICAL),
    ],
)
def test_compute_risk_band_handles_invalid_values_safely(invalid, expected):
    # Never raises; returns a deterministic band.
    assert compute_risk_band(invalid) is expected


def test_compute_risk_band_band_value_is_str_enum():
    band = compute_risk_band(20)
    assert band == "critical"
    assert band.value == "critical"


@pytest.mark.parametrize(
    "internal,expected_100",
    [
        (None, None),
        (15, 60),
        (17, 68),
        (18, 72),
        (19, 76),
        (20, 80),
        (25, 100),
    ],
)
def test_compute_score_100_matches_frontend_normalization(internal, expected_100):
    assert compute_score_100(internal) == expected_100


def test_score_100_and_band_agree_at_every_boundary():
    """The 0–100 thresholds (80/70/60) and the internal banding never disagree."""
    for internal in range(5, 26):
        s100 = compute_score_100(internal)
        band = compute_risk_band(internal)
        if s100 >= 80:
            assert band is RiskBandValue.CRITICAL
        elif s100 >= 70:
            assert band is RiskBandValue.HIGH
        elif s100 >= 60:
            assert band is RiskBandValue.MEDIUM
        else:
            assert band is RiskBandValue.BELOW_60
