"""Slice 3B.2AJ — the Swagger/OpenAPI documentation contract.

The 3B.2AI audit found runtime authentication correct but the OpenAPI document
silent about it: no ``securitySchemes``, no per-operation ``security``, no
Authorize button, and no 401/403 anywhere. These tests pin the remediation.

Two invariants matter more than the individual assertions:

1. **Security metadata follows the auth dependency, not a hand-maintained list.**
   ``AdminBearer`` is declared on :func:`app.auth.get_current_user` and
   ``SubscriberBearer`` on :func:`app.auth.supabase.get_current_subscriber`, so
   an operation is documented as protected exactly when it is protected. The
   test that matters most is
   :func:`test_security_metadata_matches_the_runtime_dependency_boundary`, which
   derives the expectation from the dependency graph rather than restating it.

2. **Hidden is not deleted.** Every route hidden from Swagger must still be
   mounted and still enforce its guard.

The schemes use ``auto_error=False`` precisely so they cannot become a second
authorization implementation — the runtime tests below prove the existing 401
semantics are untouched.
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SPEC = app.openapi()
HTTP_METHODS = ("get", "post", "put", "patch", "delete")

ADMIN_SCHEME = "AdminBearer"
SUBSCRIBER_SCHEME = "SubscriberBearer"

#: Documented operations that legitimately take no bearer token.
UNAUTHENTICATED_OPERATIONS = frozenset({
    ("GET", "/api/alerts"),                # public product data
    ("POST", "/api/v1/auth/login"),        # bootstrap
    ("POST", "/api/v1/stripe/webhook"),    # Stripe signature verification
})


def _documented_operations() -> dict[tuple[str, str], dict]:
    return {
        (method.upper(), path): op
        for path, item in SPEC["paths"].items()
        for method, op in item.items()
        if method in HTTP_METHODS
    }


def _schemes_for(operation: dict) -> set[str]:
    return {name for requirement in operation.get("security", []) for name in requirement}


def _mounted_routes() -> dict[tuple[str, str], APIRoute]:
    """Every (method, full path) the app serves, including hidden ones."""
    found: dict[tuple[str, str], APIRoute] = {}

    def walk(router, prefix=""):
        for route in getattr(router, "routes", []) or []:
            if type(route).__name__ == "_IncludedRouter":
                ctx = getattr(route, "include_context", None)
                inner = getattr(route, "original_router", None)
                walk(inner, prefix + (getattr(ctx, "prefix", "") or ""))
            elif isinstance(route, APIRoute):
                for method in route.methods - {"HEAD", "OPTIONS"}:
                    found[(method, prefix + route.path)] = route
            elif getattr(route, "routes", None):
                walk(route, prefix + (getattr(route, "path", "") or ""))

    walk(app)
    return found


def _auth_dependency_names(route: APIRoute) -> set[str]:
    names: set[str] = set()

    def walk(dependant):
        name = getattr(dependant.call, "__name__", None)
        if name:
            names.add(name)
        for sub in dependant.dependencies:
            walk(sub)

    for sub in route.dependant.dependencies:
        walk(sub)
    return names


OPERATIONS = _documented_operations()
ROUTES = _mounted_routes()

#: Hidden from Swagger by slice 3B.2AJ — operational or currently unconsumed.
HIDDEN_OPERATIONS = frozenset({
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/raw-items"),
    ("GET", "/api/v1/raw-items/{item_id}"),
    ("GET", "/api/v1/stats"),
    ("GET", "/api/v1/sources"),
    ("GET", "/api/v1/sources/{source_id}"),
    ("PATCH", "/api/v1/sources/{source_id}"),
    ("GET", "/api/v1/sources/{source_id}/runs"),
    ("POST", "/api/v1/sources/{source_id}/trigger"),
    ("POST", "/api/v1/alerts/process"),
    ("GET", "/api/v1/events"),
    ("GET", "/api/v1/events/{event_id}"),
    ("GET", "/api/v1/client/alerts"),
    ("GET", "/api/v1/client/alerts/{alert_id}"),
})


# ===========================================================================
# A. securitySchemes exist
# ===========================================================================


def test_security_schemes_are_declared():
    schemes = SPEC["components"].get("securitySchemes")
    assert schemes, "no securitySchemes — Swagger UI would render no Authorize button"
    assert set(schemes) == {ADMIN_SCHEME, SUBSCRIBER_SCHEME}


@pytest.mark.parametrize("name", [ADMIN_SCHEME, SUBSCRIBER_SCHEME])
def test_schemes_are_http_bearer_jwt_and_nothing_exotic(name):
    """HTTP Bearer only — no Basic, API-key or OAuth2 flow the app does not use."""
    scheme = SPEC["components"]["securitySchemes"][name]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert scheme["bearerFormat"] == "JWT"
    assert scheme.get("description"), "each scheme must say where its token comes from"


def test_the_two_schemes_are_described_as_distinct_token_systems():
    admin = SPEC["components"]["securitySchemes"][ADMIN_SCHEME]["description"]
    subscriber = SPEC["components"]["securitySchemes"][SUBSCRIBER_SCHEME]["description"]
    assert "auth/login" in admin
    assert "Supabase" in subscriber
    assert "not interchangeable" in subscriber.lower()


# ===========================================================================
# B / C. Admin and Subscriber operations carry the right scheme
# ===========================================================================


#: Every operation reached through `get_current_user` (directly, or nested
#: inside `require_admin`'s chain) — i.e. everything that carries the
#: `AdminBearer` scheme, meaning "an Internal JWT from POST /api/v1/auth/login
#: was presented." That is an authentication-mechanism grouping, not a role
#: grouping: `auth/me` and `change-password` are any-authenticated-user routes
#: (`get_current_user` only, no role check — see app/auth/__init__.py), while
#: `/api/v1/alerts*` and every `/api/v1/admin/*` route below additionally
#: require `role == "admin"` (`require_admin`) since the Pre-Launch Admin
#: Authorization Hardening slice (18 August 2026). The role-level distinction
#: is covered separately by `test_403_is_documented_only_where_a_role_or_subscription_check_exists`
#: below and by `test_route_inventory.py::test_admin_api_routes_keep_the_admin_guard`
#: — this list only proves the shared bearer scheme.
ADMIN_OPERATIONS = [
    ("GET", "/api/v1/auth/me"),
    ("POST", "/api/v1/auth/change-password"),
    ("GET", "/api/v1/alerts"),
    ("GET", "/api/v1/alerts/{alert_id}"),
    ("POST", "/api/v1/alerts/{alert_id}/review"),
    ("GET", "/api/v1/admin/alerts/categories"),
    ("GET", "/api/v1/admin/intelligence-briefs"),
    ("POST", "/api/v1/admin/intelligence-briefs"),
    ("GET", "/api/v1/admin/intelligence-briefs/{brief_id}"),
    ("PUT", "/api/v1/admin/intelligence-briefs/{brief_id}"),
    ("POST", "/api/v1/admin/intelligence-briefs/{brief_id}/publish"),
    ("POST", "/api/v1/admin/intelligence-briefs/{brief_id}/archive"),
    ("POST", "/api/v1/admin/intelligence-briefs/{brief_id}/feature"),
    ("POST", "/api/v1/admin/intelligence-briefs/{brief_id}/unfeature"),
    ("POST", "/api/v1/admin/intelligence-briefs/{brief_id}/featured-image"),
    ("DELETE", "/api/v1/admin/intelligence-briefs/{brief_id}/featured-image"),
    ("GET", "/api/v1/admin/sources/health"),
    ("GET", "/api/v1/admin/sources/{source_id}/health"),
    ("GET", "/api/v1/admin/system/health-summary"),
]

SUBSCRIBER_OPERATIONS = [
    ("GET", "/api/v1/subscriber/me"),
    ("GET", "/api/v1/subscriber/access"),
    ("GET", "/api/v1/subscriber/alerts"),
    ("GET", "/api/v1/subscriber/alerts/top"),
    ("GET", "/api/v1/subscriber/alerts/stats"),
    ("GET", "/api/v1/subscriber/alerts/categories"),
    ("GET", "/api/v1/subscriber/alerts/{alert_id}"),
    ("GET", "/api/v1/subscriber/search/alerts"),
    ("GET", "/api/v1/subscriber/intelligence-briefs"),
    ("GET", "/api/v1/subscriber/intelligence-briefs/featured"),
    ("GET", "/api/v1/subscriber/intelligence-briefs/{slug}"),
    ("POST", "/api/v1/billing/checkout"),
    ("POST", "/api/v1/billing/portal"),
    ("GET", "/api/v1/billing/status"),
    ("POST", "/api/v1/billing/sync"),
]


@pytest.mark.parametrize("method,path", ADMIN_OPERATIONS)
def test_admin_operations_require_the_admin_bearer(method, path):
    assert (method, path) in OPERATIONS, f"{method} {path} vanished from Swagger"
    assert _schemes_for(OPERATIONS[(method, path)]) == {ADMIN_SCHEME}


@pytest.mark.parametrize("method,path", SUBSCRIBER_OPERATIONS)
def test_subscriber_and_billing_operations_require_the_subscriber_bearer(method, path):
    assert (method, path) in OPERATIONS, f"{method} {path} vanished from Swagger"
    assert _schemes_for(OPERATIONS[(method, path)]) == {SUBSCRIBER_SCHEME}


#: Pre-Launch Admin Authorization Hardening: the Swagger-visible Alert
#: operations that moved from get_current_user-only to require_admin.
HARDENED_ADMIN_ALERT_OPERATIONS = [
    ("GET", "/api/v1/alerts"),
    ("GET", "/api/v1/alerts/{alert_id}"),
    ("POST", "/api/v1/alerts/{alert_id}/review"),
]


@pytest.mark.parametrize("method,path", HARDENED_ADMIN_ALERT_OPERATIONS)
def test_hardened_alert_operations_document_both_401_and_403(method, path):
    """These used to document 401 only (get_current_user, no role check).
    They now require the admin role (require_admin), so Swagger must show both:
    401 for no/invalid token, 403 for a valid-but-non-admin Internal JWT.
    """
    responses = OPERATIONS[(method, path)]["responses"]
    assert "401" in responses
    assert "403" in responses
    assert _schemes_for(OPERATIONS[(method, path)]) == {ADMIN_SCHEME}


def test_auth_me_and_change_password_do_not_claim_admin_role_enforcement():
    """These stay any-authenticated-Internal-JWT-user routes (get_current_user
    only, no require_admin) — hardening the Alert surface must not spread to
    account/identity operations that were never Admin-role-gated."""
    for key in (("GET", "/api/v1/auth/me"), ("POST", "/api/v1/auth/change-password")):
        responses = OPERATIONS[key]["responses"]
        assert "401" in responses
        assert "403" not in responses, f"{key} must not claim role enforcement it doesn't have"


def test_admin_and_subscriber_operation_lists_cover_every_protected_operation():
    """No documented operation is left unclassified by the two lists above."""
    listed = set(ADMIN_OPERATIONS) | set(SUBSCRIBER_OPERATIONS) | UNAUTHENTICATED_OPERATIONS
    assert set(OPERATIONS) == listed, (
        f"unclassified: {sorted(set(OPERATIONS) - listed)}; "
        f"stale: {sorted(listed - set(OPERATIONS))}"
    )


def test_security_metadata_matches_the_runtime_dependency_boundary():
    """The whole point: documentation follows the dependency, not a second list.

    Derived from the route dependency graph, so a future route that gains or
    loses an auth dependency without matching security metadata fails here.
    """
    mismatches = []
    for key, operation in OPERATIONS.items():
        route = ROUTES[key]
        deps = _auth_dependency_names(route)
        expected: set[str] = set()
        if "get_current_user" in deps:
            expected.add(ADMIN_SCHEME)
        if "get_current_subscriber" in deps:
            expected.add(SUBSCRIBER_SCHEME)
        if _schemes_for(operation) != expected:
            mismatches.append((key, sorted(_schemes_for(operation)), sorted(expected)))
    assert not mismatches, f"security metadata diverged from dependencies: {mismatches}"


# ===========================================================================
# D / E / F. Intentionally unauthenticated operations
# ===========================================================================


@pytest.mark.parametrize("method,path", sorted(UNAUTHENTICATED_OPERATIONS))
def test_intentionally_unauthenticated_operations_carry_no_bearer(method, path):
    assert (method, path) in OPERATIONS
    assert _schemes_for(OPERATIONS[(method, path)]) == set()


def test_no_other_documented_operation_is_unauthenticated():
    """Exactly three, and they are the three intended ones."""
    open_ops = {key for key, op in OPERATIONS.items() if not _schemes_for(op)}
    assert open_ops == UNAUTHENTICATED_OPERATIONS
    assert len(open_ops) == 3


def test_stripe_webhook_is_documented_as_signature_authenticated_not_bearer():
    operation = OPERATIONS[("POST", "/api/v1/stripe/webhook")]
    assert "security" not in operation or not operation["security"]
    tag_names = {tag["name"]: tag["description"] for tag in SPEC.get("tags", [])}
    assert "signature" in tag_names["stripe-webhook"].lower()


# ===========================================================================
# G / H. Hidden from Swagger, retained in the service
# ===========================================================================


@pytest.mark.parametrize("method,path", sorted(HIDDEN_OPERATIONS))
def test_hidden_operations_are_absent_from_openapi(method, path):
    assert (method, path) not in OPERATIONS


@pytest.mark.parametrize("method,path", sorted(HIDDEN_OPERATIONS))
def test_hidden_operations_are_still_mounted(method, path):
    assert (method, path) in ROUTES, "hidden from Swagger must not mean removed"


@pytest.mark.parametrize("method,path", sorted(HIDDEN_OPERATIONS))
def test_hidden_operations_keep_their_authentication(method, path):
    """Hiding is a documentation change — the guards are untouched."""
    if (method, path) == ("GET", "/api/v1/health"):
        pytest.skip("the health probe is unauthenticated by design")
    deps = _auth_dependency_names(ROUTES[(method, path)])
    assert deps & {
        "get_current_user",
        "require_admin",
        "require_subscriber_or_admin",
    }, f"{method} {path} lost its guard while being hidden"


def test_swagger_exposes_no_internal_implementation_surface():
    """None of the internals the audit called out may be documented."""
    documented_paths = set(SPEC["paths"])
    for fragment in (
        "/raw-items",
        "/api/v1/sources",
        "/api/v1/stats",
        "/alerts/process",
        "/api/v1/events",
        "/api/v1/client",
        "/api/v1/health",
    ):
        assert not any(p.startswith(fragment) for p in documented_paths), (
            f"internal surface {fragment} is documented"
        )


# ===========================================================================
# I / J. Review request enums
# ===========================================================================


def test_review_status_enum_matches_the_runtime_validation_exactly():
    """The endpoint has always enforced this set; Swagger now shows it."""
    from app.api.alerts import submit_review  # noqa: F401  (import proves the module loads)

    schema = SPEC["components"]["schemas"]["AlertReviewCreate"]["properties"]["review_status"]
    assert schema["enum"] == ["approved", "false_positive", "edited"]
    assert "review_status" in SPEC["components"]["schemas"]["AlertReviewCreate"]["required"]


def test_adjusted_risk_level_enum_is_the_risk_level_domain():
    schema = SPEC["components"]["schemas"]["AlertReviewCreate"]["properties"]["adjusted_risk_level"]
    enums = [branch["enum"] for branch in schema["anyOf"] if "enum" in branch]
    assert enums == [["low", "medium", "high", "critical"]]
    assert {"type": "null"} in schema["anyOf"], "the field stays optional"


def test_review_response_model_still_accepts_historical_statuses():
    """``alert_reviews`` holds five values written by backfill tooling, not the API.

    Tightening the *response* model would break reading those rows back.
    """
    read = SPEC["components"]["schemas"]["AlertReviewRead"]["properties"]["review_status"]
    assert "enum" not in str(read), "AlertReviewRead.review_status must stay unconstrained"


@pytest.mark.parametrize(
    "status", ["approved", "false_positive", "edited"]
)
def test_valid_review_statuses_still_validate(status):
    from app.schemas.alert import AlertReviewCreate

    assert AlertReviewCreate(review_status=status).review_status == status


@pytest.mark.parametrize("status", ["Approved", "rejected", "", "historical_review"])
def test_invalid_review_statuses_are_rejected(status):
    from pydantic import ValidationError

    from app.schemas.alert import AlertReviewCreate

    with pytest.raises(ValidationError):
        AlertReviewCreate(review_status=status)


@pytest.mark.parametrize(
    "value,expected",
    [("low", "low"), ("medium", "medium"), ("high", "high"), ("critical", "critical"),
     ("High", "high"), ("  CRITICAL  ", "critical")],
)
def test_adjusted_risk_level_accepts_and_normalises_supported_values(value, expected):
    """Case-insensitivity is preserved: the endpoint always wrote ``.lower()``."""
    from app.schemas.alert import AlertReviewCreate

    payload = AlertReviewCreate(review_status="edited", adjusted_risk_level=value)
    assert payload.adjusted_risk_level == expected


@pytest.mark.parametrize("value", ["urgent", "below_60", "none"])
def test_adjusted_risk_level_rejects_values_outside_the_column_domain(value):
    from pydantic import ValidationError

    from app.schemas.alert import AlertReviewCreate

    with pytest.raises(ValidationError):
        AlertReviewCreate(review_status="edited", adjusted_risk_level=value)


def test_adjusted_risk_level_remains_optional():
    from app.schemas.alert import AlertReviewCreate

    assert AlertReviewCreate(review_status="approved").adjusted_risk_level is None


# ===========================================================================
# K / L. Field documentation
# ===========================================================================


def test_key_signals_update_semantics_are_documented():
    description = SPEC["components"]["schemas"]["IntelligenceBriefUpdate"]["properties"][
        "key_signals"
    ]["description"]
    lowered = description.lower()
    assert "omit" in lowered and "preserved" in lowered
    assert "`[]`" in description and "clear" in lowered
    assert "replace" in lowered
    assert "never appended" in lowered


def test_key_signals_is_still_an_array_of_strings_everywhere():
    for model in (
        "IntelligenceBriefCreate",
        "IntelligenceBriefUpdate",
        "IntelligenceBriefDetail",
        "SubscriberBriefDetail",
    ):
        prop = SPEC["components"]["schemas"][model]["properties"]["key_signals"]
        branches = prop["anyOf"]
        assert {"items": {"type": "string"}, "type": "array"} in branches, model


def test_category_total_description_corrects_the_misreading():
    description = SPEC["components"]["schemas"]["AlertCategoriesResponse"]["properties"][
        "total"
    ]["description"]
    assert "alerts" in description.lower()
    assert "not" in description.lower() and "categor" in description.lower()


# ===========================================================================
# M / N. Regression guards
# ===========================================================================


@pytest.mark.parametrize(
    "path",
    [
        "/api/alerts/top",
        "/api/alerts/stats",
        "/api/alerts/{alert_id}",
        "/api/search/alerts",
        "/login",
        "/dashboard",
    ],
)
def test_retired_routes_remain_absent(path):
    assert path not in SPEC["paths"]
    assert not any(p == path for _, p in ROUTES)


def test_public_teaser_item_contract_is_unchanged():
    """The approved five fields, and nothing more."""
    item = SPEC["components"]["schemas"]["PublicTeaserAlertRead"]["properties"]
    assert set(item) == {"title", "risk_band", "category", "published_at", "summary"}


def test_top_alerts_response_contract_is_unchanged():
    response = SPEC["components"]["schemas"]["SubscriberTopAlertsResponse"]["properties"]
    assert set(response) == {"alerts", "is_fallback", "message"}


def test_no_response_model_changed_shape():
    """Only ``AlertReviewCreate`` (a request model) was allowed to change.

    Guards against a description edit accidentally altering a payload.
    """
    expectations = {
        "SubscriberAlertRead": {
            "id", "title", "summary", "category", "risk_level", "signal_score",
            "source_name", "source_url", "source_published_at", "published_at",
            "risk_band", "processed_at",
        },
        "AlertCategoriesResponse": {"categories", "total"},
        "AlertCategoryRead": {"value", "label", "count"},
        "AlertReviewRead": {
            "id", "alert_id", "user_id", "review_status", "edited_summary",
            "adjusted_risk_level", "reviewed_at",
        },
    }
    for model, fields in expectations.items():
        assert set(SPEC["components"]["schemas"][model]["properties"]) == fields, model


def test_category_enum_still_lists_the_six_canonical_values():
    assert SPEC["components"]["schemas"]["AlertCategoryRead"]["properties"]["value"]["enum"] == [
        "Investment Fraud",
        "Cybercrime",
        "Consumer Scam",
        "Money Laundering",
        "Cryptocurrency Fraud",
        "Other",
    ]


# ===========================================================================
# 401 / 403 documentation
# ===========================================================================


def test_every_protected_operation_documents_401():
    missing = [
        key
        for key, op in OPERATIONS.items()
        if key not in UNAUTHENTICATED_OPERATIONS and "401" not in op["responses"]
    ]
    assert not missing, f"protected operations without a documented 401: {missing}"


def test_403_is_documented_only_where_a_role_or_subscription_check_exists():
    """Never claim a 403 an operation cannot emit.

    ``require_admin`` and ``require_active_subscription`` are the only
    dependencies that raise 403. ``get_current_active_user`` nominally does too,
    but ``get_current_user`` has already rejected inactive accounts with a 401,
    so that branch is unreachable and must not be documented.
    """
    wrong = []
    for key, operation in OPERATIONS.items():
        deps = _auth_dependency_names(ROUTES[key])
        can_403 = bool(deps & {"require_admin", "require_active_subscription"})
        documents_403 = "403" in operation["responses"]
        if can_403 != documents_403:
            wrong.append((key, documents_403, can_403))
    assert not wrong, f"403 documentation does not match the guards: {wrong}"


def test_identity_routes_document_401_but_not_403():
    """A token is required; a subscription is not."""
    for key in (("GET", "/api/v1/subscriber/me"), ("GET", "/api/v1/subscriber/access")):
        responses = OPERATIONS[key]["responses"]
        assert "401" in responses
        assert "403" not in responses


# ===========================================================================
# Tag organisation
# ===========================================================================


def test_tag_metadata_orders_the_reference_public_first_admin_last():
    names = [tag["name"] for tag in SPEC["tags"]]
    assert names[0] == "public"
    assert names.index("auth") < names.index("subscriber")
    assert names.index("subscriber") < names.index("intelligence-briefs-admin")
    assert all(tag.get("description") for tag in SPEC["tags"])


def test_every_documented_tag_has_metadata():
    used = {tag for op in OPERATIONS.values() for tag in op.get("tags", [])}
    described = {tag["name"] for tag in SPEC["tags"]}
    assert used <= described, f"tags without metadata: {sorted(used - described)}"


def test_tag_metadata_describes_no_hidden_surface():
    """Tag metadata must not advertise route groups that are no longer documented."""
    used = {tag for op in OPERATIONS.values() for tag in op.get("tags", [])}
    described = {tag["name"] for tag in SPEC["tags"]}
    assert described <= used, f"metadata for absent tags: {sorted(described - used)}"


# ===========================================================================
# Final counts
# ===========================================================================


def test_final_documented_surface_counts():
    assert len(SPEC["paths"]) == 34
    assert len(OPERATIONS) == 37
    protected = {k for k, op in OPERATIONS.items() if _schemes_for(op)}
    assert len(protected) == 34
    assert len(OPERATIONS) - len(protected) == 3


def test_service_still_serves_every_route_it_did():
    assert len(ROUTES) == 51


# ===========================================================================
# Final Alert Contract and Documentation Refinement (18 August 2026):
# the Admin/Subscriber risk_band contract as a durable OpenAPI regression,
# not a one-time manual `app.openapi()` inspection that can silently drift.
# ===========================================================================


def _query_param_names(method: str, path: str) -> set[str]:
    params = OPERATIONS[(method.upper(), path)].get("parameters", [])
    return {p["name"] for p in params if p.get("in") == "query"}


#: The exact, final Admin Alerts query contract — see app/api/alerts.py.
#: Deliberately exhaustive (not just "risk_level absent") so a silently
#: renamed or dropped shared filter fails here too.
ADMIN_ALERTS_QUERY_PARAMS = {
    "category", "source_id", "source", "keyword", "start_date", "end_date",
    "published_from", "published_to", "source_published_from", "source_published_to",
    "is_relevant", "is_published", "publish_decision", "pending_review_reason",
    "risk_band", "is_excluded", "is_manual_hold", "published_by_rule",
    "publication_state_source", "limit", "offset",
}

#: The exact, final Subscriber Alerts query contract — see app/api/subscriber.py.
SUBSCRIBER_ALERTS_QUERY_PARAMS = {
    "risk_band", "category", "source", "published_from", "published_to",
    "source_published_from", "source_published_to", "limit", "offset",
}


def test_admin_alerts_openapi_query_parameters_are_exactly_the_final_contract():
    assert _query_param_names("GET", "/api/v1/alerts") == ADMIN_ALERTS_QUERY_PARAMS


def test_subscriber_alerts_openapi_query_parameters_are_exactly_the_final_contract():
    assert _query_param_names("GET", "/api/v1/subscriber/alerts") == SUBSCRIBER_ALERTS_QUERY_PARAMS


def test_neither_alerts_endpoint_documents_risk_level_as_a_filter():
    assert "risk_level" not in _query_param_names("GET", "/api/v1/alerts")
    assert "risk_level" not in _query_param_names("GET", "/api/v1/subscriber/alerts")


def test_admin_start_date_is_documented_by_its_public_alias_not_the_internal_variable_name():
    """The route param is named ``since`` in Python (``alias="start_date"``) —
    OpenAPI must show the public alias, never the internal variable name."""
    names = _query_param_names("GET", "/api/v1/alerts")
    assert "start_date" in names
    assert "since" not in names


def _resolve_schema(node: dict) -> dict:
    """Follow a single $ref one level, the only nesting these params use."""
    ref = node.get("$ref")
    if ref is None:
        # anyOf: [{"$ref": ...}, {"type": "null"}] — the Optional[...] shape.
        for branch in node.get("anyOf", []):
            if "$ref" in branch:
                ref = branch["$ref"]
                break
    if ref is None:
        return node
    assert ref.startswith("#/components/schemas/")
    return SPEC["components"]["schemas"][ref.removeprefix("#/components/schemas/")]


@pytest.mark.parametrize("path", ["/api/v1/alerts", "/api/v1/subscriber/alerts"])
def test_risk_band_query_param_resolves_to_the_exact_four_canonical_values(path):
    """Not just "the parameter exists" — the enum it resolves to (following a
    $ref into components/schemas if FastAPI put it there) must be exactly the
    four canonical RiskBandValue members, nothing added or dropped."""
    params = OPERATIONS[("GET", path)]["parameters"]
    risk_band_param = next(p for p in params if p["name"] == "risk_band")
    resolved = _resolve_schema(risk_band_param["schema"])
    assert resolved.get("enum") == ["critical", "high", "medium", "below_60"]


def test_risk_band_value_component_schema_is_the_single_enum_definition():
    """Guards against a second, drift-prone enum/Literal being introduced
    instead of reusing RiskBandValue."""
    schema = SPEC["components"]["schemas"]["RiskBandValue"]
    assert schema["enum"] == ["critical", "high", "medium", "below_60"]
    assert schema["type"] == "string"


def test_subscriber_alert_read_exposes_the_four_documented_alert_fields_with_distinct_descriptions():
    props = SPEC["components"]["schemas"]["SubscriberAlertRead"]["properties"]
    for field in ("risk_band", "published_at", "source_published_at", "processed_at"):
        assert field in props, f"{field} missing from SubscriberAlertRead"
        description = props[field].get("description", "")
        assert description, f"{field} has no OpenAPI description"

    # The three timestamps must not read as interchangeable paraphrases of
    # each other — each description names something the others don't.
    assert "HiddenAlerts" in props["published_at"]["description"]
    assert "source" in props["source_published_at"]["description"].lower()
    assert "processed" in props["processed_at"]["description"].lower()
    assert "never recomputed" in props["risk_band"]["description"].lower()


def test_top_alerts_response_references_the_same_subscriber_alert_read_item_schema():
    """Top Alerts must not have its own parallel item schema that could drift
    from the paginated feed's — both are SubscriberAlertRead."""
    response = SPEC["components"]["schemas"]["SubscriberTopAlertsResponse"]["properties"]["alerts"]
    resolved = _resolve_schema(response.get("items", response))
    assert resolved is SPEC["components"]["schemas"]["SubscriberAlertRead"]


def test_public_teaser_schema_does_not_leak_score_or_risk_level():
    """Regression guard for the exact leak class the teaser is designed to prevent."""
    props = SPEC["components"]["schemas"]["PublicTeaserAlertRead"]["properties"]
    for forbidden in ("signal_score", "risk_level", "source_name", "source_url", "id"):
        assert forbidden not in props, f"{forbidden} leaked onto the public teaser"


def test_admin_date_filter_descriptions_are_semantically_distinct():
    """published_from/to, source_published_from/to and start_date/end_date must
    each name the timestamp they filter — never generic, interchangeable "date"
    wording that could let one be mistaken for another."""
    params = {p["name"]: p for p in OPERATIONS[("GET", "/api/v1/alerts")]["parameters"]}
    published = (params["published_from"]["description"] + params["published_to"]["description"]).lower()
    source_published = (
        params["source_published_from"]["description"] + params["source_published_to"]["description"]
    ).lower()
    operational = (params["start_date"]["description"] + params["end_date"]["description"]).lower()

    assert "hiddenalerts" in published and "published_at" in published
    assert "source" in source_published and "article" in source_published
    assert "processed_at" in operational
    # The three descriptions must not be identical to one another.
    assert len({published, source_published, operational}) == 3


def test_subscriber_date_filter_descriptions_are_semantically_distinct():
    params = {p["name"]: p for p in OPERATIONS[("GET", "/api/v1/subscriber/alerts")]["parameters"]}
    published = (params["published_from"]["description"] + params["published_to"]["description"]).lower()
    source_published = (
        params["source_published_from"]["description"] + params["source_published_to"]["description"]
    ).lower()
    assert "published" in published
    assert "source" in source_published and "article" in source_published
    assert published != source_published
