"""Shared risk-score / risk-level helpers (M3 final — Ken-approved bands).

The internal 5-factor `signal_score_total` is on a 5–25 scale. The frontend
displays a normalized `risk_score` on a 0–100 scale; `risk_level` is derived
strictly from that 0–100 value with Ken's bands:

    >= 70  -> high
    40-69  -> medium
    1-39   -> low

Formula: risk_score = round(signal_score_total / 25 * 100)
Worked examples (per Ken's May 06 message): 17 -> 68, 19 -> 76, 21 -> 84.

These helpers are imported by the public, admin, and client API mappers so the
formula and bands live in exactly one place.
"""
from __future__ import annotations

# Public 0–100 thresholds. Internal-score equivalents on the 5–25 scale:
#   >=18 internal -> >=72 on 0-100 -> high
#   10-17 internal -> 40-68 on 0-100 -> medium
#   <=9 internal -> <=36 on 0-100 -> low
RISK_HIGH_THRESHOLD = 70
RISK_MEDIUM_THRESHOLD = 40


def risk_score_100(signal_score_total: int | None) -> int | None:
    """Convert internal 5–25 signal score to a 0–100 risk_score.

    Returns None if the input is None. Examples: 17 -> 68, 18 -> 72, 19 -> 76.
    """
    if signal_score_total is None:
        return None
    return round(signal_score_total / 25 * 100)


def risk_level_from_100(
    risk_score: int | None,
    *,
    title_case: bool = False,
) -> str | None:
    """Derive risk level from the 0–100 risk_score (Ken's M3 final bands).

    Returns "high" / "medium" / "low" lowercase by default; pass title_case=True
    to get "High" / "Medium" / "Low" for fields that document title case.
    """
    if risk_score is None:
        return None
    if risk_score >= RISK_HIGH_THRESHOLD:
        return "High" if title_case else "high"
    if risk_score >= RISK_MEDIUM_THRESHOLD:
        return "Medium" if title_case else "medium"
    return "Low" if title_case else "low"


def risk_level_from_score(
    signal_score_total: int | None,
    *,
    title_case: bool = False,
) -> str | None:
    """Convenience wrapper: derive risk_level directly from internal score.

    Equivalent to `risk_level_from_100(risk_score_100(signal_score_total))`.
    """
    return risk_level_from_100(risk_score_100(signal_score_total), title_case=title_case)
