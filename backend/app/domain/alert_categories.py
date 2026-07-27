"""Canonical Alert category vocabulary.

The single definition of the alert taxonomy, shared by the AI classifier, the V1
publishing policy and the category metadata APIs. Values are stored verbatim in
``processed_alerts.primary_category`` and returned by the API as filter values,
so they must not be reworded, reordered or reused for other product areas.

Deliberately free of ORM and pydantic imports so the pure policy modules can
depend on it without pulling in the database layer.
"""
from typing import Literal

AlertCategory = Literal[
    "Investment Fraud",
    "Cybercrime",
    "Consumer Scam",
    "Money Laundering",
    "Cryptocurrency Fraud",
    "Other",
]

# Canonical API/display order. Spelled out rather than derived from the Literal
# so the sequence is reviewable on its own; a test asserts the two stay in sync.
ALERT_CATEGORIES: tuple[AlertCategory, ...] = (
    "Investment Fraud",
    "Cybercrime",
    "Consumer Scam",
    "Money Laundering",
    "Cryptocurrency Fraud",
    "Other",
)

# Catch-all bucket. The V1 policy always routes this to manual review.
OTHER_CATEGORY = "Other"

# Categories Ken approved for V1 auto-publish. This is an explicit allowlist, not
# "every category except Other": adding a category to the taxonomy above must
# never make it auto-publishable on its own — approving it for publication is a
# separate decision that has to be made here.
PUBLISHABLE_ALERT_CATEGORIES: frozenset[str] = frozenset(
    {
        "Investment Fraud",
        "Cybercrime",
        "Consumer Scam",
        "Money Laundering",
        "Cryptocurrency Fraud",
    }
)
