import logging
import os
import sys
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings

# Configure basic logging with timestamp
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Update uvicorn loggers to use the same configuration
for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uvicorn_logger = logging.getLogger(logger_name)
    uvicorn_logger.handlers.clear()
    uvicorn_logger.propagate = True

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    if settings.scheduler_enabled:
        from app.scheduler.jobs import scheduler, setup_scheduler
        setup_scheduler()
        scheduler.start()

    yield

    # Shutdown
    if settings.scheduler_enabled:
        from app.scheduler.jobs import scheduler
        if scheduler.running:
            scheduler.shutdown(wait=False)


# Swagger tag order and one-line descriptions. FastAPI renders tags in this
# order, so the reference reads public → auth → subscriber → admin rather than
# alphabetically. Names match the tags already declared on the routers, so no
# route-level churn was needed; only tags belonging to schema-visible routes are
# listed here.
OPENAPI_TAGS = [
    {"name": "public", "description": "Unauthenticated Landing Page teaser. No token required."},
    {"name": "auth", "description": "Admin login and profile. `POST /auth/login` issues the internal Admin JWT."},
    {"name": "subscriber", "description": "Subscriber account and alert APIs. Supabase authentication required; paid-content routes additionally require an active subscription."},
    {"name": "subscriber-intelligence-briefs", "description": "Published Intelligence Briefs for subscribers."},
    {"name": "billing", "description": "Stripe checkout, customer portal and subscription status."},
    {"name": "alerts", "description": "Admin Alerts — list, detail and review decisions."},
    {"name": "alerts-admin", "description": "Admin alert metadata, such as the canonical category list."},
    {"name": "intelligence-briefs-admin", "description": "Intelligence Brief CMS — create, edit, lifecycle and featured image."},
    {"name": "source-health", "description": "Admin monitoring — per-source collector health and the system rollup."},
    {"name": "stripe-webhook", "description": "Stripe event receiver. Authenticated by Stripe signature, not by a bearer token."},
]

app = FastAPI(
    title="HiddenAlerts",
    description=(
        "AI Fraud Intelligence Monitoring System.\n\n"
        "**Authentication.** Two separate bearer tokens are in use and they are "
        "not interchangeable — pick the matching entry under **Authorize**:\n\n"
        "- `AdminBearer` — internal HiddenAlerts JWT from `POST /api/v1/auth/login`, "
        "for `/api/v1/auth`, Admin Alerts, Admin Intelligence Briefs and Admin Monitoring.\n"
        "- `SubscriberBearer` — Supabase access token, for `/api/v1/subscriber/...` "
        "and `/api/v1/billing/...`.\n\n"
        "Three operations take no bearer token: `GET /api/alerts` (public teaser), "
        "`POST /api/v1/auth/login` (bootstrap) and `POST /api/v1/stripe/webhook` "
        "(verified by Stripe signature).\n\n"
        "Operational and internal routes are omitted from this document; they "
        "remain available in the running service."
    ),
    version="0.2.0",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

# CORS: lock to the frontend origin when ``FRONTEND_BASE_URL`` is configured,
# else stay open for the MVP public feed. GET/POST/PUT cover the read feeds,
# billing/checkout, and the admin CMS write endpoints. Subscriber auth uses
# Authorization: Bearer (Supabase token); no cookies → allow_credentials stays
# at its False default.
_cors_origins = [settings.frontend_base_url.rstrip("/")] if settings.frontend_base_url else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# User-uploaded media (admin-uploaded Intelligence Brief featured images),
# served at /uploads/intelligence-briefs/<file>. This is the only static mount:
# the app serves no static assets of its own since the Jinja dashboard was
# removed. The directory is created if missing so the mount succeeds on a fresh
# deployment.
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

# Register routers
from app.api._responses import (  # noqa: E402
    ADMIN_AUTH_RESPONSES,
    SUBSCRIBER_AUTH_RESPONSES,
    UNAUTHORIZED,
)
from app.api.health import router as health_router  # noqa: E402
from app.api.sources import router as sources_router  # noqa: E402
from app.api.source_health import router as source_health_router  # noqa: E402
from app.api.raw_items import router as raw_items_router  # noqa: E402
from app.api.alerts import router as alerts_router  # noqa: E402
from app.api.alerts_admin import router as alerts_admin_router  # noqa: E402
from app.api.auth import router as auth_router  # noqa: E402
from app.api.client_alerts import router as client_alerts_router  # noqa: E402
from app.api.public_alerts import router as public_alerts_router  # noqa: E402
from app.api.subscriber import router as subscriber_router  # noqa: E402
from app.api.billing import router as billing_router  # noqa: E402
from app.api.stripe_webhooks import router as stripe_webhooks_router  # noqa: E402
from app.api.intelligence_briefs_admin import router as intelligence_briefs_admin_router  # noqa: E402
from app.api.intelligence_briefs_subscriber import router as intelligence_briefs_subscriber_router  # noqa: E402

# ``include_in_schema=False`` below hides operational and currently unconsumed
# routes from Swagger so /docs reads as the supported integration reference.
# They remain fully registered and callable with unchanged authentication — this
# is a documentation-visibility change only, not a removal. See
# backend/reports/swagger_openapi_fix_3b2aj_20260811.md for the inventory.
app.include_router(health_router, prefix="/api/v1", include_in_schema=False)  # infra probe
app.include_router(sources_router, prefix="/api/v1", include_in_schema=False)  # source config/ops
app.include_router(
    source_health_router, prefix="/api/v1", responses=ADMIN_AUTH_RESPONSES
)  # Admin read-only observability
app.include_router(raw_items_router, prefix="/api/v1", include_in_schema=False)  # ingestion internals
app.include_router(
    alerts_router, prefix="/api/v1", responses=ADMIN_AUTH_RESPONSES
)  # Admin Alerts/Events — require_admin (Pre-Launch Admin Authorization Hardening)
app.include_router(
    alerts_admin_router, prefix="/api/v1", responses=ADMIN_AUTH_RESPONSES
)  # Admin alert metadata
app.include_router(auth_router, prefix="/api/v1", responses=UNAUTHORIZED)
app.include_router(client_alerts_router, prefix="/api/v1", include_in_schema=False)  # no known consumer
app.include_router(
    subscriber_router, prefix="/api/v1", responses=UNAUTHORIZED
)  # Supabase-authenticated paid feed; per-route 403 where a subscription is required
app.include_router(
    billing_router, prefix="/api/v1", responses=UNAUTHORIZED
)  # Stripe checkout / portal / status
app.include_router(stripe_webhooks_router, prefix="/api/v1")  # Stripe webhook (no auth; signature-verified)
app.include_router(
    intelligence_briefs_admin_router, prefix="/api/v1", responses=ADMIN_AUTH_RESPONSES
)  # Admin CMS
app.include_router(
    intelligence_briefs_subscriber_router,
    prefix="/api/v1",
    responses=SUBSCRIBER_AUTH_RESPONSES,
)  # Paid subscriber feed
app.include_router(public_alerts_router)  # No prefix — /api/alerts public feed
