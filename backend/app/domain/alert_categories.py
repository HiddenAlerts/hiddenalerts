"""Canonical Alert category vocabulary.

The single definition of the alert taxonomy, shared by the AI classifier, the V1
publishing policy and the category metadata APIs. Values are stored verbatim in
``processed_alerts.primary_category`` and returned by the API as filter values,
so they must not be reworded, reordered or reused for other product areas.

Deliberately free of ORM and pydantic imports so the pure policy modules can
depend on it without pulling in the database layer.
"""
from typing import Literal, get_args

AlertCategory = Literal[
    "Investment Fraud",
    "Cybercrime",
    "Consumer Scam",
    "Money Laundering",
    "Cryptocurrency Fraud",
    "Other",
]

# Derived from the Literal so the type and the sequence can never drift apart.
# get_args preserves declaration order, which is the order the API returns.
ALERT_CATEGORIES: tuple[str, ...] = get_args(AlertCategory)

# Catch-all bucket. The V1 policy always routes this to manual review.
OTHER_CATEGORY = "Other"

# Categories eligible for V1 auto-publish. Kept as a separate name because this
# is a policy allowlist, not part of the taxonomy: a future category would need
# an explicit decision to become auto-publishable.
PUBLISHABLE_ALERT_CATEGORIES: frozenset[str] = frozenset(
    category for category in ALERT_CATEGORIES if category != OTHER_CATEGORY
)
