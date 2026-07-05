"""V1 risk-band mapping (Slice 2 — pure, deterministic, no DB, no side effects).

Maps the internal 5–25 ``signal_score_total`` to a V1 :class:`RiskBandValue`.

The bands are defined on the frontend 0–100 scale (Critical 80–100, High 70–79,
Medium 60–69, below 60 excluded) and equivalently on the internal 5–25 scale:

    internal 20–25  -> 0–100 80–100  -> critical
    internal 18–19  -> 0–100 72–76   -> high
    internal 15–17  -> 0–100 60–68   -> medium
    internal  5–14  -> 0–100 20–56   -> below_60   (and None/invalid)

Banding is done on the **internal** thresholds (``>=20 / >=18 / >=15``) because
the pipeline stores the internal score and the boundaries coincide exactly with
the 0–100 normalisation used by the frontend (``round(internal / 25 * 100)``),
so the two definitions never disagree. ``compute_score_100`` reuses the single
source of truth in :mod:`app.api._risk` for the normalisation itself.

Nothing here is wired into the live pipeline yet (Slice 5 does that).
"""
from __future__ import annotations

from app.api._risk import risk_score_100
from app.pipeline.publishing.constants import RiskBandValue

# Internal-score (5–25) lower bounds for each band. Equivalent 0–100 bounds in
# the module docstring. Kept here so risk-band logic has one local source.
_CRITICAL_MIN_INTERNAL = 20  # 0–100: 80
_HIGH_MIN_INTERNAL = 18      # 0–100: 70 (72 at internal 18)
_MEDIUM_MIN_INTERNAL = 15    # 0–100: 60


def compute_score_100(signal_score_total: int | None) -> int | None:
    """Normalise the internal 5–25 score to the frontend 0–100 scale.

    Thin, explicit alias over :func:`app.api._risk.risk_score_100` so V1 code
    has a publishing-local entry point without duplicating the formula. Returns
    ``None`` when the input is ``None``.
    """
    return risk_score_100(signal_score_total)


def compute_risk_band(signal_score_total: int | None) -> RiskBandValue:
    """Map an internal ``signal_score_total`` (5–25) to a :class:`RiskBandValue`.

    Pure and total: never raises. ``None`` and any value below the medium floor
    (including negative or otherwise invalid values) map to ``BELOW_60``; any
    value at or above the critical floor (including out-of-range highs) maps to
    ``CRITICAL``. This keeps the function safe for unexpected inputs while
    remaining consistent with the frontend normalisation at every real boundary.
    """
    if signal_score_total is None:
        return RiskBandValue.BELOW_60
    if signal_score_total >= _CRITICAL_MIN_INTERNAL:
        return RiskBandValue.CRITICAL
    if signal_score_total >= _HIGH_MIN_INTERNAL:
        return RiskBandValue.HIGH
    if signal_score_total >= _MEDIUM_MIN_INTERNAL:
        return RiskBandValue.MEDIUM
    return RiskBandValue.BELOW_60
